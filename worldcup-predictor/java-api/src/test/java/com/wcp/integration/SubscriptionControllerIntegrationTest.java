package com.wcp.integration;

import static org.hamcrest.Matchers.hasSize;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.node.ObjectNode;
import com.stripe.exception.StripeException;
import com.wcp.dto.response.SubscriptionPlanResponse;
import com.wcp.dto.response.PaymentInitResponse;
import com.wcp.service.SubscriptionService;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.test.web.servlet.request.MockHttpServletRequestBuilder;

import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;

/**
 * Subscription / payments controller chain — pricing catalogue,
 * create-order auth gate, request-DTO regex validation, current
 * subscription lookup, cancel auto-renew. These cover the failure
 * modes the unit tests for SubscriptionService can't see end-to-end —
 * in particular the @Valid annotations on CreateSubscriptionRequest
 * (which silently 400'd Stripe orders for weeks before the regex was
 * fixed).
 */
class SubscriptionControllerIntegrationTest extends IntegrationTestBase {

    @Autowired private SubscriptionService subscriptionService;

    /** Register + login a new user, returning their access token. */
    private String registerAccess(String email) throws Exception {
        ObjectNode body = objectMapper.createObjectNode()
                .put("email", email)
                .put("password", "Password123");
        MvcResult res = mockMvc.perform(post("/api/v1/auth/register")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body.toString()))
                .andExpect(status().isCreated())
                .andReturn();
        return objectMapper.readTree(res.getResponse().getContentAsString())
                .get("accessToken").asText();
    }

    /** Build a /subscriptions/create request with the given channel. */
    private MockHttpServletRequestBuilder createOrder(String tier, String planType, String channel) {
        ObjectNode body = objectMapper.createObjectNode()
                .put("tier", tier)
                .put("planType", planType)
                .put("paymentChannel", channel);
        return post("/api/v1/subscriptions/create")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body.toString());
    }

    // --- /plans (public) -------------------------------------------------

    @Test
    @DisplayName("GET /subscriptions/plans is anonymous-readable and returns 4 catalogue rows")
    void plansPublicAndComplete() throws Exception {
        when(mlApiClient.fxUsdCny()).thenReturn(7.20);

        mockMvc.perform(get("/api/v1/subscriptions/plans"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$", hasSize(4)))
                .andExpect(jsonPath("$[?(@.tier=='basic' && @.planType=='monthly')]").exists())
                .andExpect(jsonPath("$[?(@.tier=='premium' && @.planType=='worldcup_pass')]").exists());

        // Direct service call so we can verify the FX-driven CNY column.
        List<SubscriptionPlanResponse> plans = subscriptionService.plans();
        SubscriptionPlanResponse basicMonthly = plans.stream()
                .filter(p -> p.tier().equals("basic") && p.planType().equals("monthly"))
                .findFirst().orElseThrow();
        // 999 cents × 7.20 = 7192.8 → rounds to 7193 fen.
        assert basicMonthly.priceUsd() == 999;
        assert basicMonthly.priceCny() == 7193;
    }

    // --- /create (auth) --------------------------------------------------

    @Test
    @DisplayName("POST /subscriptions/create without bearer token → 401/403")
    void createRequiresAuth() throws Exception {
        mockMvc.perform(createOrder("basic", "monthly", "alipay"))
                .andExpect(result -> {
                    int code = result.getResponse().getStatus();
                    assert code == 401 || code == 403
                            : "anonymous order creation must be denied, got " + code;
                });
    }

    @Test
    @DisplayName("POST /subscriptions/create happy path returns the order envelope")
    void createHappyPath() throws Exception {
        String access = registerAccess("buyer@user.test");
        when(mlApiClient.fxUsdCny()).thenReturn(7.20);

        mockMvc.perform(createOrder("basic", "monthly", "alipay")
                .header("Authorization", "Bearer " + access))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.orderNo").exists())
                .andExpect(jsonPath("$.paymentChannel").value("alipay"))
                .andExpect(jsonPath("$.amountUsd").value(999))
                .andExpect(jsonPath("$.amountCny").value(7193));
    }

    @Test
    @DisplayName("POST /subscriptions/create with stripe channel falls back to stub when SDK is unconfigured")
    void stripeChannelFallsBackToStub() throws Exception {
        String access = registerAccess("intl@user.test");
        when(mlApiClient.fxUsdCny()).thenReturn(7.20);
        when(stripeClient.isConfigured()).thenReturn(false);

        mockMvc.perform(createOrder("basic", "monthly", "stripe")
                .header("Authorization", "Bearer " + access))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.paymentChannel").value("stripe"))
                .andExpect(jsonPath("$.paymentParams.sdkPayload.mode").value("stub"));
    }

    @Test
    @DisplayName("POST /subscriptions/create with stripe channel + configured SDK → checkoutUrl")
    void stripeChannelHappyPath() throws Exception {
        String access = registerAccess("intl2@user.test");
        when(mlApiClient.fxUsdCny()).thenReturn(7.20);
        when(stripeClient.isConfigured()).thenReturn(true);

        com.stripe.model.checkout.Session session =
                org.mockito.Mockito.mock(com.stripe.model.checkout.Session.class);
        when(session.getId()).thenReturn("cs_test_int");
        when(session.getUrl()).thenReturn("https://checkout.stripe.com/c/pay/cs_test_int");
        when(stripeClient.createCheckoutSession(anyString(), anyInt(), anyString(), anyString()))
                .thenReturn(session);

        mockMvc.perform(createOrder("basic", "monthly", "stripe")
                .header("Authorization", "Bearer " + access))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.paymentParams.sdkPayload.mode").value("stripe"))
                .andExpect(jsonPath("$.paymentParams.sdkPayload.checkoutUrl")
                        .value("https://checkout.stripe.com/c/pay/cs_test_int"))
                .andExpect(jsonPath("$.paymentParams.sdkPayload.sessionId").value("cs_test_int"));
    }

    @Test
    @DisplayName("@Pattern rejects an unknown tier with 400")
    void invalidTierRejected() throws Exception {
        String access = registerAccess("badtier@user.test");

        mockMvc.perform(createOrder("vip", "monthly", "alipay")
                .header("Authorization", "Bearer " + access))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("@Pattern rejects an unknown paymentChannel with 400")
    void invalidChannelRejected() throws Exception {
        String access = registerAccess("badchan@user.test");

        // Pin the regex against a payload that would have been silently 400'd
        // before the Stripe addition. PayPal is intentionally not on the list.
        mockMvc.perform(createOrder("basic", "monthly", "paypal")
                .header("Authorization", "Bearer " + access))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("@Pattern rejects an unknown planType with 400")
    void invalidPlanTypeRejected() throws Exception {
        String access = registerAccess("badplan@user.test");

        mockMvc.perform(createOrder("basic", "lifetime", "alipay")
                .header("Authorization", "Bearer " + access))
                .andExpect(status().isBadRequest());
    }

    // --- /current --------------------------------------------------------

    @Test
    @DisplayName("GET /subscriptions/current anonymous → 401/403")
    void currentRequiresAuth() throws Exception {
        mockMvc.perform(get("/api/v1/subscriptions/current"))
                .andExpect(result -> {
                    int code = result.getResponse().getStatus();
                    assert code == 401 || code == 403;
                });
    }

    @Test
    @DisplayName("GET /subscriptions/current with no active sub returns {active:false, tier:free}")
    void currentReturnsFreeWhenNoSubscription() throws Exception {
        String access = registerAccess("free@user.test");

        mockMvc.perform(get("/api/v1/subscriptions/current")
                .header("Authorization", "Bearer " + access))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.active").value(false))
                .andExpect(jsonPath("$.tier").value("free"));
    }

    // --- /cancel ---------------------------------------------------------

    @Test
    @DisplayName("POST /subscriptions/cancel anonymous → 401/403")
    void cancelRequiresAuth() throws Exception {
        mockMvc.perform(post("/api/v1/subscriptions/cancel"))
                .andExpect(result -> {
                    int code = result.getResponse().getStatus();
                    assert code == 401 || code == 403;
                });
    }

    @Test
    @DisplayName("POST /subscriptions/cancel with no active sub → 404")
    void cancelWithoutActiveSubReturns404() throws Exception {
        String access = registerAccess("nosub@user.test");

        mockMvc.perform(post("/api/v1/subscriptions/cancel")
                .header("Authorization", "Bearer " + access))
                .andExpect(status().isNotFound());
    }

    // --- /payments/callback/stripe ---------------------------------------

    @Test
    @DisplayName("POST /payments/callback/stripe without Stripe-Signature header → 400")
    void stripeWebhookNeedsSignatureHeader() throws Exception {
        // Endpoint is public (no auth required) — signature header IS the
        // auth. Missing header should fail fast at the controller.
        mockMvc.perform(post("/api/v1/payments/callback/stripe")
                .contentType("application/json")
                .content("{}"))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("POST /payments/callback/stripe with invalid signature → 400 (Stripe will retry)")
    void stripeWebhookInvalidSigRejected() throws Exception {
        when(stripeClient.verifyWebhook(anyString(), anyString()))
                .thenThrow(new com.stripe.exception.SignatureVerificationException(
                        "bad sig", "Stripe-Signature"));

        mockMvc.perform(post("/api/v1/payments/callback/stripe")
                .header("Stripe-Signature", "t=0,v1=bogus")
                .contentType("application/json")
                .content("{}"))
                .andExpect(status().isBadRequest());
    }
}
