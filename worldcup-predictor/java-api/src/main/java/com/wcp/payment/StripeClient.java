package com.wcp.payment;

import com.stripe.Stripe;
import com.stripe.exception.SignatureVerificationException;
import com.stripe.exception.StripeException;
import com.stripe.model.Event;
import com.stripe.model.checkout.Session;
import com.stripe.net.Webhook;
import com.stripe.param.checkout.SessionCreateParams;
import com.wcp.config.WcpProperties;
import jakarta.annotation.PostConstruct;
import java.util.Map;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

/**
 * Thin wrapper around the Stripe Java SDK. Two responsibilities:
 *
 * <ul>
 *   <li>{@link #createCheckoutSession} — build a hosted Checkout URL for a
 *       single subscription order, carrying the merchant {@code orderNo}
 *       in {@code client_reference_id} so the webhook can match the
 *       payment back to our row.</li>
 *   <li>{@link #verifyWebhook} — verify the {@code Stripe-Signature}
 *       header against the configured endpoint-secret and return the
 *       parsed {@link Event}.</li>
 * </ul>
 *
 * Tests inject a mock of this class so they never reach the live Stripe
 * API.
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class StripeClient {

    private final WcpProperties wcpProperties;

    @PostConstruct
    void configureGlobalKey() {
        WcpProperties.Stripe cfg = wcpProperties.stripe();
        if (cfg != null && cfg.isConfigured()) {
            Stripe.apiKey = cfg.secretKey();
            log.info("stripe_sdk_configured key_suffix={}", lastFour(cfg.secretKey()));
        } else {
            log.info("stripe_sdk_unconfigured running_in_stub_mode=true");
        }
    }

    /** True once a secret-key is set; controllers should 503 / fall back otherwise. */
    public boolean isConfigured() {
        WcpProperties.Stripe cfg = wcpProperties.stripe();
        return cfg != null && cfg.isConfigured();
    }

    /**
     * Build a Stripe Checkout Session for one order.
     *
     * @param orderNo merchant-side identifier — echoed back on the webhook
     *                as {@code client_reference_id}.
     * @param amountUsdCents the integer minor-units amount the user pays.
     * @param productName line-item label shown in the Checkout UI.
     * @param customerEmail pre-fill for the checkout form (optional).
     * @return the created Session, exposing {@link Session#getUrl()} for
     *         the redirect target the frontend opens.
     */
    public Session createCheckoutSession(
            String orderNo,
            int amountUsdCents,
            String productName,
            String customerEmail
    ) throws StripeException {
        WcpProperties.Stripe cfg = wcpProperties.stripe();
        SessionCreateParams.Builder builder = SessionCreateParams.builder()
                .setMode(SessionCreateParams.Mode.PAYMENT)
                .setSuccessUrl(cfg.successUrl())
                .setCancelUrl(cfg.cancelUrl())
                .setClientReferenceId(orderNo)
                .putMetadata("orderNo", orderNo)
                .addLineItem(SessionCreateParams.LineItem.builder()
                        .setQuantity(1L)
                        .setPriceData(SessionCreateParams.LineItem.PriceData.builder()
                                .setCurrency("usd")
                                .setUnitAmount((long) amountUsdCents)
                                .setProductData(
                                        SessionCreateParams.LineItem.PriceData.ProductData.builder()
                                                .setName(productName)
                                                .build()
                                )
                                .build())
                        .build());
        if (customerEmail != null && !customerEmail.isBlank()) {
            builder.setCustomerEmail(customerEmail);
        }
        return Session.create(builder.build());
    }

    /**
     * Verify a webhook payload against the configured endpoint-secret.
     *
     * @throws SignatureVerificationException if the signature doesn't match
     *         — caller should respond 400 and Stripe will retry until our
     *         endpoint-secret rotation lines up.
     */
    public Event verifyWebhook(String payload, String signatureHeader)
            throws SignatureVerificationException {
        WcpProperties.Stripe cfg = wcpProperties.stripe();
        if (cfg == null || cfg.webhookSecret() == null || cfg.webhookSecret().isBlank()) {
            throw new IllegalStateException(
                    "stripe.webhook-secret is not configured; refusing to accept callback");
        }
        return Webhook.constructEvent(payload, signatureHeader, cfg.webhookSecret());
    }

    /** Pull the merchant {@code orderNo} out of a `checkout.session.completed` event. */
    public String orderNoFromEvent(Event event) {
        Object obj = event.getDataObjectDeserializer().getObject().orElse(null);
        if (obj instanceof Session session) {
            String ref = session.getClientReferenceId();
            if (ref != null && !ref.isBlank()) {
                return ref;
            }
            Map<String, String> meta = session.getMetadata();
            if (meta != null) {
                return meta.getOrDefault("orderNo", "");
            }
        }
        return "";
    }

    /** Pull the Stripe payment intent id so we have a channel-side trade ref. */
    public String paymentIntentFromEvent(Event event) {
        Object obj = event.getDataObjectDeserializer().getObject().orElse(null);
        if (obj instanceof Session session) {
            return session.getPaymentIntent();
        }
        return null;
    }

    /** Pull the charge amount in cents from a `checkout.session.completed` event. */
    public int amountTotalCentsFromEvent(Event event) {
        Object obj = event.getDataObjectDeserializer().getObject().orElse(null);
        if (obj instanceof Session session && session.getAmountTotal() != null) {
            return session.getAmountTotal().intValue();
        }
        return 0;
    }

    private static String lastFour(String key) {
        if (key == null || key.length() < 4) return "????";
        return key.substring(key.length() - 4);
    }
}
