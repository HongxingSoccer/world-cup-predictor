package com.wcp.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.stripe.exception.SignatureVerificationException;
import com.stripe.model.Event;
import com.stripe.model.checkout.Session;
import com.wcp.dto.response.PaymentInitResponse;
import com.wcp.exception.ApiException;
import com.wcp.model.Payment;
import com.wcp.model.User;
import com.wcp.payment.StripeClient;
import com.wcp.repository.PaymentRepository;
import com.wcp.repository.UserRepository;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.Mockito;
import org.mockito.junit.jupiter.MockitoExtension;

/**
 * Stripe payment flow — init (Checkout Session) + webhook (verify, match,
 * amount-check, idempotency, activate). Mocks the Stripe SDK behind
 * {@link StripeClient} so the tests never reach the real Stripe API.
 *
 * Stripe is the only payment channel today with a real SDK behind it, so
 * any regression here means international users either can't start a
 * subscription or pay-and-don't-get-access. Worth pinning.
 */
@ExtendWith(MockitoExtension.class)
class StripePaymentTest {

    @Mock private PaymentRepository paymentRepository;
    @Mock private UserRepository userRepository;
    @Mock private SubscriptionService subscriptionService;
    @Mock private StripeClient stripeClient;

    @InjectMocks private PaymentService paymentService;

    // ---------------------------------------------------------------------
    // Shared fixtures
    // ---------------------------------------------------------------------

    private User stubUser() {
        return User.builder()
                .id(7L).uuid(UUID.randomUUID())
                .email("intl@user.test")
                .passwordHash("h")
                .subscriptionTier("free")
                .locale("zh-CN").timezone("Asia/Shanghai")
                .active(true).role("user")
                .build();
    }

    private Payment stubStripePayment() {
        return Payment.builder()
                .id(1L)
                .userId(7L)
                .orderNo("WCP-12345")
                .paymentChannel("stripe")
                .amountCny(7193)
                .status("pending")
                .build();
    }

    // ---------------------------------------------------------------------
    // initPayment for stripe channel
    // ---------------------------------------------------------------------

    @Nested
    @DisplayName("initPayment(stripe channel)")
    class InitStripe {

        @Test
        @DisplayName("falls back to stub payload when Stripe creds are missing (local dev)")
        void unconfiguredFallsBack() throws Exception {
            when(stripeClient.isConfigured()).thenReturn(false);

            Payment payment = stubStripePayment();
            var plan = new com.wcp.dto.response.SubscriptionPlanResponse(
                    "basic", "monthly", 999, 7193, 30, "Basic · Monthly"
            );

            PaymentInitResponse out = paymentService.initPayment(payment, plan, stubUser());

            @SuppressWarnings("unchecked")
            var sdk = (java.util.Map<String, Object>) out.paymentParams().get("sdkPayload");
            assertThat(sdk).containsEntry("mode", "stub");
            assertThat(sdk).containsEntry("reason", "stripe_secret_key_missing");
            // Don't hit Stripe when unconfigured.
            verify(stripeClient, never()).createCheckoutSession(anyString(), anyInt(), anyString(), anyString());
        }

        @Test
        @DisplayName("calls Stripe + returns the hosted Checkout URL")
        void happyPath() throws Exception {
            when(stripeClient.isConfigured()).thenReturn(true);
            Session session = Mockito.mock(Session.class);
            when(session.getId()).thenReturn("cs_test_abc");
            when(session.getUrl()).thenReturn("https://checkout.stripe.com/c/pay/cs_test_abc");
            when(stripeClient.createCheckoutSession(
                    Mockito.eq("WCP-12345"),
                    Mockito.eq(999),
                    Mockito.contains("Basic"),
                    Mockito.eq("intl@user.test")
            )).thenReturn(session);
            when(paymentRepository.save(any(Payment.class))).thenAnswer(inv -> inv.getArgument(0));

            Payment payment = stubStripePayment();
            var plan = new com.wcp.dto.response.SubscriptionPlanResponse(
                    "basic", "monthly", 999, 7193, 30, "Basic · Monthly"
            );

            PaymentInitResponse out = paymentService.initPayment(payment, plan, stubUser());

            @SuppressWarnings("unchecked")
            var sdk = (java.util.Map<String, Object>) out.paymentParams().get("sdkPayload");
            assertThat(sdk)
                    .containsEntry("mode", "stripe")
                    .containsEntry("checkoutUrl", "https://checkout.stripe.com/c/pay/cs_test_abc")
                    .containsEntry("sessionId", "cs_test_abc");
            assertThat(out.amountUsd()).isEqualTo(999);
            // We persist the session id immediately so reconciliation has a
            // channel-side handle before the webhook lands.
            assertThat(payment.getChannelTradeNo()).isEqualTo("cs_test_abc");
        }

        @Test
        @DisplayName("Stripe SDK failure surfaces as 400 to the caller")
        void stripeFailureBecomes400() throws Exception {
            when(stripeClient.isConfigured()).thenReturn(true);
            when(stripeClient.createCheckoutSession(anyString(), anyInt(), anyString(), anyString()))
                    .thenThrow(new com.stripe.exception.InvalidRequestException(
                            "rate_limited", "param", "code", null, 400, null));

            var plan = new com.wcp.dto.response.SubscriptionPlanResponse(
                    "basic", "monthly", 999, 7193, 30, "Basic · Monthly"
            );

            assertThatThrownBy(() ->
                    paymentService.initPayment(stubStripePayment(), plan, stubUser())
            )
                    .isInstanceOf(ApiException.class)
                    .extracting(ex -> ((ApiException) ex).getStatus().value())
                    .isEqualTo(400);
        }
    }

    // ---------------------------------------------------------------------
    // handleStripeWebhook
    // ---------------------------------------------------------------------

    @Nested
    @DisplayName("handleStripeWebhook")
    class WebhookHandling {

        @Test
        @DisplayName("rejects bad signature with 400 (Stripe will retry until our secret rotates)")
        void badSignatureRejected() throws SignatureVerificationException {
            when(stripeClient.verifyWebhook(anyString(), anyString()))
                    .thenThrow(new SignatureVerificationException("bad sig", "Stripe-Signature"));

            assertThatThrownBy(() -> paymentService.handleStripeWebhook("{}", "t=0,v1=bad"))
                    .isInstanceOf(ApiException.class)
                    .extracting(ex -> ((ApiException) ex).getStatus().value())
                    .isEqualTo(400);
        }

        @Test
        @DisplayName("no-ops for non-checkout-completed event types (2xx without state change)")
        void unrelatedEventsIgnored() throws Exception {
            Event event = Mockito.mock(Event.class);
            when(event.getType()).thenReturn("payment_intent.processing");
            when(event.getId()).thenReturn("evt_abc");
            when(stripeClient.verifyWebhook(anyString(), anyString())).thenReturn(event);

            paymentService.handleStripeWebhook("{}", "t=0,v1=ok");

            verify(paymentRepository, never()).findByOrderNo(anyString());
            verify(subscriptionService, never()).activateSubscription(any(), any(), any());
        }

        @Test
        @DisplayName("rejects checkout.completed event with missing client_reference_id")
        void missingOrderNoRejected() throws Exception {
            Event event = stubCheckoutEvent("", 999);
            when(stripeClient.verifyWebhook(anyString(), anyString())).thenReturn(event);

            assertThatThrownBy(() -> paymentService.handleStripeWebhook("{}", "t=0,v1=ok"))
                    .isInstanceOf(ApiException.class)
                    .hasMessageContaining("client_reference_id");
        }

        @Test
        @DisplayName("idempotent — re-delivered events on an already-paid order skip the activate")
        void idempotentOnPaidPayment() throws Exception {
            Event event = stubCheckoutEvent("WCP-12345", 999);
            when(stripeClient.verifyWebhook(anyString(), anyString())).thenReturn(event);

            Payment paid = stubStripePayment();
            paid.setStatus("paid");
            when(paymentRepository.findByOrderNo("WCP-12345")).thenReturn(Optional.of(paid));

            paymentService.handleStripeWebhook("{}", "t=0,v1=ok");

            verify(subscriptionService, never()).activateSubscription(any(), any(), any());
            verify(paymentRepository, never()).save(any());
        }

        @Test
        @DisplayName("rejects tampered amount (charged total ≠ plan price)")
        void amountTamperingRejected() throws Exception {
            // Stripe reports a $1 charge for an order that should have been $9.99.
            Event event = stubCheckoutEvent("WCP-12345", 100);
            when(stripeClient.verifyWebhook(anyString(), anyString())).thenReturn(event);

            Payment pending = stubStripePayment();
            when(paymentRepository.findByOrderNo("WCP-12345")).thenReturn(Optional.of(pending));
            when(subscriptionService.plans()).thenReturn(java.util.List.of(
                    new com.wcp.dto.response.SubscriptionPlanResponse(
                            "basic", "monthly", 999, 7193, 30, "Basic · Monthly"
                    )
            ));

            assertThatThrownBy(() -> paymentService.handleStripeWebhook("{}", "t=0,v1=ok"))
                    .isInstanceOf(ApiException.class)
                    .hasMessageContaining("amount mismatch");

            // No tier grant on a mismatched amount.
            verify(subscriptionService, never()).activateSubscription(any(), any(), any());
        }

        @Test
        @DisplayName("happy path — marks paid, persists trade ref, activates subscription")
        void happyPath() throws Exception {
            Event event = stubCheckoutEvent("WCP-12345", 999);
            when(stripeClient.verifyWebhook(anyString(), anyString())).thenReturn(event);
            when(stripeClient.paymentIntentFromEvent(event)).thenReturn("pi_test_xyz");

            Payment pending = stubStripePayment();
            User user = stubUser();
            when(paymentRepository.findByOrderNo("WCP-12345")).thenReturn(Optional.of(pending));
            when(paymentRepository.save(any(Payment.class))).thenAnswer(inv -> inv.getArgument(0));
            when(userRepository.findById(7L)).thenReturn(Optional.of(user));
            when(subscriptionService.plans()).thenReturn(java.util.List.of(
                    new com.wcp.dto.response.SubscriptionPlanResponse(
                            "basic", "monthly", 999, 7193, 30, "Basic · Monthly"
                    )
            ));

            paymentService.handleStripeWebhook("{}", "t=0,v1=ok");

            assertThat(pending.getStatus()).isEqualTo("paid");
            assertThat(pending.getPaidAt()).isNotNull();
            assertThat(pending.getChannelTradeNo()).isEqualTo("pi_test_xyz");
            verify(subscriptionService, times(1)).activateSubscription(
                    Mockito.eq(pending), any(), Mockito.eq(user));
        }
    }

    // ---------------------------------------------------------------------
    // Helpers
    // ---------------------------------------------------------------------

    private Event stubCheckoutEvent(String orderNo, int amountCents) {
        // All stubs lenient — not every test path consumes every accessor
        // (e.g. event.getId() only logs in the early-return branch). With
        // strict mode the unused stubs would fail the test.
        Event event = Mockito.mock(Event.class);
        Mockito.lenient().when(event.getType()).thenReturn("checkout.session.completed");
        Mockito.lenient().when(event.getId()).thenReturn("evt_stub");
        Mockito.lenient().when(stripeClient.orderNoFromEvent(event)).thenReturn(orderNo);
        Mockito.lenient().when(stripeClient.amountTotalCentsFromEvent(event)).thenReturn(amountCents);
        return event;
    }
}
