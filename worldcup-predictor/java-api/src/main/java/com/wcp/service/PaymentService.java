package com.wcp.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.stripe.exception.SignatureVerificationException;
import com.stripe.exception.StripeException;
import com.stripe.model.Event;
import com.stripe.model.checkout.Session;
import com.wcp.config.WcpProperties;
import com.wcp.dto.response.PaymentInitResponse;
import com.wcp.dto.response.SubscriptionPlanResponse;
import com.wcp.exception.ApiException;
import com.wcp.exception.PaymentChannelDisabledException;
import com.wcp.model.Payment;
import com.wcp.model.User;
import com.wcp.payment.StripeClient;
import com.wcp.repository.PaymentRepository;
import com.wcp.repository.UserRepository;
import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Lazy;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Payment-channel adapter + callback handler.
 *
 * <p>Stripe is fully integrated (signed Checkout sessions + webhook
 * verification). The Alipay / WeChat code paths are still stub
 * implementations — the signature check would accept any non-empty
 * payload — so they're gated behind {@code wcp.payments.enable-cn-channels}
 * and default to OFF in any environment exposed to the public internet.
 * The dev profile sets the flag to {@code true} so the existing test
 * suite still exercises the control flow.
 *
 * <p>Idempotency contract: a callback for an order that's already
 * {@code paid} short-circuits with success — provider retries are common.
 */
@Service
@Slf4j
public class PaymentService {

    private static final java.util.Set<String> CN_CHANNELS =
            java.util.Set.of("alipay", "wechat_pay");

    private final PaymentRepository paymentRepository;
    private final UserRepository userRepository;
    private final SubscriptionService subscriptionService;
    private final StripeClient stripeClient;
    private final WcpProperties wcpProperties;

    /**
     * Explicit constructor (rather than Lombok's {@code @RequiredArgsConstructor})
     * so the {@link Lazy} annotation lands directly on the constructor
     * parameter — without it Spring can't break the
     * {@code SubscriptionService → PaymentService → SubscriptionService} cycle.
     */
    public PaymentService(
            PaymentRepository paymentRepository,
            UserRepository userRepository,
            @Lazy SubscriptionService subscriptionService,
            StripeClient stripeClient,
            WcpProperties wcpProperties
    ) {
        this.paymentRepository = paymentRepository;
        this.userRepository = userRepository;
        this.subscriptionService = subscriptionService;
        this.stripeClient = stripeClient;
        this.wcpProperties = wcpProperties;
    }

    /** Public probe so the controller can short-circuit disabled CN callbacks to 404. */
    public boolean isCnChannelsEnabled() {
        WcpProperties.Payments cfg = wcpProperties.payments();
        return cfg != null && cfg.enableCnChannels();
    }

    /** Build the SDK-bound payment params returned to the front-end. */
    public PaymentInitResponse initPayment(
            Payment payment, SubscriptionPlanResponse plan, User user) {
        String channel = payment.getPaymentChannel();

        // Refuse CN-channel orders before persisting any side-effects when
        // the SDK is not integrated yet — otherwise a forged callback
        // against a real `pending` Payment row can flip status to `paid`
        // (the verifySignature stub accepts any non-empty body).
        if (CN_CHANNELS.contains(channel) && !isCnChannelsEnabled()) {
            log.warn("payment_init_blocked_cn_channel_disabled channel={}", channel);
            throw new PaymentChannelDisabledException(channel);
        }

        Map<String, Object> params = new HashMap<>();
        params.put("orderNo", payment.getOrderNo());
        params.put("amount", payment.getAmountCny());
        params.put("amountUsd", plan.priceUsd());
        params.put("subject", plan.displayName());
        params.put("userUuid", user.getUuid().toString());

        // Stripe is the only channel with a real SDK behind it today. The
        // CN channels reach this code path only when explicitly enabled
        // (dev / test profile); they hand back a typed stub marker so
        // callers can detect dev-stub mode instead of the previous
        // free-form "TODO-Phase-3.5" string.
        if ("stripe".equals(channel)) {
            params.put("sdkPayload", buildStripePayload(payment, plan, user));
        } else {
            params.put("sdkPayload", Map.of(
                    "mode", "stub",
                    "reason", "cn_channel_sdk_not_integrated"
            ));
        }

        log.info(
                "payment_init order={} channel={} amount_cny={} amount_usd={}",
                payment.getOrderNo(),
                channel,
                payment.getAmountCny(),
                plan.priceUsd()
        );
        return new PaymentInitResponse(
                payment.getOrderNo(),
                channel,
                plan.priceUsd(),
                payment.getAmountCny(),
                params
        );
    }

    /**
     * Build the Stripe-specific portion of the SDK payload. When the
     * environment has Stripe credentials wired we hit the real API and
     * return a hosted Checkout URL the frontend redirects the user to.
     * Without credentials (local dev) we ship a placeholder so the
     * order-creation contract still resolves end-to-end for testing.
     */
    private Map<String, Object> buildStripePayload(
            Payment payment, SubscriptionPlanResponse plan, User user) {
        if (!stripeClient.isConfigured()) {
            log.warn(
                    "stripe_unconfigured falling_back_to_stub order={}",
                    payment.getOrderNo()
            );
            return Map.of("mode", "stub", "reason", "stripe_secret_key_missing");
        }
        try {
            Session session = stripeClient.createCheckoutSession(
                    payment.getOrderNo(),
                    plan.priceUsd(),
                    plan.displayName(),
                    user.getEmail()
            );
            // Persist the session id immediately so reconciliation has a
            // channel-side handle even before the webhook lands.
            payment.setChannelTradeNo(session.getId());
            paymentRepository.save(payment);
            return Map.of(
                    "mode", "stripe",
                    "checkoutUrl", session.getUrl(),
                    "sessionId", session.getId()
            );
        } catch (StripeException ex) {
            log.error(
                    "stripe_session_create_failed order={} code={} message={}",
                    payment.getOrderNo(),
                    ex.getCode(),
                    ex.getMessage()
            );
            throw ApiException.badRequest("stripe error: " + ex.getMessage());
        }
    }

    /**
     * Handle a Stripe webhook. The HTTP body must be passed in verbatim
     * (NOT pre-parsed to JSON) because Stripe's signature check is over
     * the exact bytes Stripe sent.
     *
     * <p>Currently handles {@code checkout.session.completed}; other event
     * types are acknowledged but no-op'd. We always 2xx after the
     * transactional update so Stripe stops retrying.
     */
    @Transactional
    public void handleStripeWebhook(String rawPayload, String signatureHeader) {
        Event event;
        try {
            event = stripeClient.verifyWebhook(rawPayload, signatureHeader);
        } catch (SignatureVerificationException ex) {
            log.error("stripe_webhook_signature_failed message={}", ex.getMessage());
            throw ApiException.badRequest("invalid stripe signature");
        }
        if (!"checkout.session.completed".equals(event.getType())) {
            log.info("stripe_webhook_ignored event_type={} id={}", event.getType(), event.getId());
            return;
        }

        String orderNo = stripeClient.orderNoFromEvent(event);
        if (orderNo == null || orderNo.isBlank()) {
            log.error("stripe_webhook_missing_order_no event_id={}", event.getId());
            throw ApiException.badRequest("stripe webhook missing client_reference_id");
        }

        Payment payment = paymentRepository.findByOrderNo(orderNo)
                .orElseThrow(() -> ApiException.notFound("payment " + orderNo));

        // Idempotency — Stripe retries until we 2xx, and `payment_intent.succeeded`
        // may also arrive shortly after `checkout.session.completed`.
        if (payment.isPaid()) {
            log.info("stripe_webhook_idempotent_skip order={}", orderNo);
            return;
        }

        // Stripe charges in USD cents. Compare against plan price to catch
        // tampered amounts before we grant access.
        int amountCharged = stripeClient.amountTotalCentsFromEvent(event);
        SubscriptionPlanResponse plan = lookupPlanForPayment(payment);
        if (amountCharged != plan.priceUsd()) {
            log.error(
                    "stripe_webhook_amount_mismatch order={} expected_usd={} got={}",
                    orderNo, plan.priceUsd(), amountCharged
            );
            throw ApiException.badRequest("amount mismatch");
        }

        payment.setStatus("paid");
        payment.setPaidAt(Instant.now());
        payment.setChannelTradeNo(stripeClient.paymentIntentFromEvent(event));
        // Stripe SDK events don't expose a JsonNode directly; keep a small
        // audit hint instead of the full payload.
        payment.setCallbackRaw(null);
        paymentRepository.save(payment);

        User user = userRepository.findById(payment.getUserId())
                .orElseThrow(() -> ApiException.notFound("user"));
        subscriptionService.activateSubscription(payment, plan, user);

        log.info(
                "stripe_webhook_activated order={} user={} tier={} plan={}",
                orderNo, user.getUuid(), plan.tier(), plan.planType()
        );
    }

    /**
     * Handle an asynchronous payment callback from Alipay or WeChat.
     *
     * @param channel one of "alipay" / "wechat_pay"
     * @param payload raw provider payload (already parsed to a JSON tree).
     */
    @Transactional
    public void handleCallback(String channel, JsonNode payload) {
        if (!verifySignature(channel, payload)) {
            log.error("payment_callback_signature_failed channel={}", channel);
            throw ApiException.badRequest("invalid signature");
        }

        String orderNo = extractOrderNo(channel, payload);
        Payment payment = paymentRepository.findByOrderNo(orderNo)
                .orElseThrow(() -> ApiException.notFound("payment " + orderNo));

        // Idempotency: providers retry callbacks until they get a 2xx.
        if (payment.isPaid()) {
            log.info("payment_callback_idempotent_skip order={}", orderNo);
            return;
        }

        int amountFromChannel = extractAmountCny(channel, payload);
        if (amountFromChannel != payment.getAmountCny()) {
            log.error(
                    "payment_callback_amount_mismatch order={} expected={} got={}",
                    orderNo, payment.getAmountCny(), amountFromChannel
            );
            throw ApiException.badRequest("amount mismatch");
        }

        payment.setStatus("paid");
        payment.setPaidAt(Instant.now());
        payment.setChannelTradeNo(extractChannelTradeNo(channel, payload));
        payment.setCallbackRaw(payload);
        paymentRepository.save(payment);

        User user = userRepository.findById(payment.getUserId())
                .orElseThrow(() -> ApiException.notFound("user"));
        SubscriptionPlanResponse plan = lookupPlanForPayment(payment);
        subscriptionService.activateSubscription(payment, plan, user);
    }

    // --- Provider-specific verification helpers (stubs) ---

    private boolean verifySignature(String channel, JsonNode payload) {
        // TODO(Phase 3.5): implement Alipay RSA2 / WeChat HMAC-SHA256 checks.
        // For now we accept any non-null payload so the rest of the flow can
        // be exercised end-to-end against test fixtures.
        return payload != null && !payload.isEmpty();
    }

    private String extractOrderNo(String channel, JsonNode payload) {
        // Both Alipay and WeChat use `out_trade_no` for the merchant order id.
        // Channel kept as a parameter so future providers can specialize.
        return payload.path("out_trade_no").asText("");
    }

    private int extractAmountCny(String channel, JsonNode payload) {
        // Alipay: total_amount in yuan (e.g. "29.90") → cents.
        // WeChat: total_fee in cents already.
        if ("alipay".equals(channel)) {
            String yuan = payload.path("total_amount").asText("0");
            return (int) Math.round(Double.parseDouble(yuan) * 100);
        }
        return payload.path("total_fee").asInt(0);
    }

    private String extractChannelTradeNo(String channel, JsonNode payload) {
        if ("alipay".equals(channel)) {
            return payload.path("trade_no").asText(null);
        }
        return payload.path("transaction_id").asText(null);
    }

    private SubscriptionPlanResponse lookupPlanForPayment(Payment payment) {
        // We can recover plan from amount alone given Phase-3's static catalogue.
        // Phase 3.5 will store plan_code on the Payment row directly.
        return subscriptionService.plans().stream()
                .filter(p -> p.priceCny() == payment.getAmountCny())
                .findFirst()
                .orElseThrow(() -> ApiException.badRequest("no plan matches amount"));
    }
}
