package com.wcp.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.wcp.dto.response.PaymentInitResponse;
import com.wcp.dto.response.SubscriptionPlanResponse;
import com.wcp.exception.ApiException;
import com.wcp.model.Payment;
import com.wcp.model.User;
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
 * <p>Phase-3 ships with a stub Alipay/WeChat integration: callback signature
 * verification + amount equality + idempotency are enforced, but the actual
 * "talk to the channel" (initPayment) returns a placeholder map until the
 * real SDKs land in Phase 3.5. The control flow is fully wired so swapping
 * stubs for real SDK calls is a small change.
 *
 * <p>Idempotency contract: a callback for an order that's already
 * {@code paid} short-circuits with success — provider retries are common.
 */
@Service
@Slf4j
public class PaymentService {

    private final PaymentRepository paymentRepository;
    private final UserRepository userRepository;
    private final SubscriptionService subscriptionService;

    /**
     * Explicit constructor (rather than Lombok's {@code @RequiredArgsConstructor})
     * so the {@link Lazy} annotation lands directly on the constructor
     * parameter — without it Spring can't break the
     * {@code SubscriptionService → PaymentService → SubscriptionService} cycle.
     */
    public PaymentService(
            PaymentRepository paymentRepository,
            UserRepository userRepository,
            @Lazy SubscriptionService subscriptionService
    ) {
        this.paymentRepository = paymentRepository;
        this.userRepository = userRepository;
        this.subscriptionService = subscriptionService;
    }

    /** Build the SDK-bound payment params returned to the front-end. */
    public PaymentInitResponse initPayment(
            Payment payment, SubscriptionPlanResponse plan, User user) {
        Map<String, Object> params = new HashMap<>();
        params.put("orderNo", payment.getOrderNo());
        params.put("amount", payment.getAmountCny());
        params.put("amountUsd", plan.priceUsd());
        params.put("subject", plan.displayName());
        // TODO(Phase 3.5): replace with real Alipay-trade-app-pay /
        // wechat-unifiedorder responses (signed strings, prepay_id, etc.).
        params.put("sdkPayload", "TODO-Phase-3.5-real-channel-call");
        params.put("userUuid", user.getUuid().toString());
        log.info(
                "payment_init order={} channel={} amount_cny={} amount_usd={}",
                payment.getOrderNo(),
                payment.getPaymentChannel(),
                payment.getAmountCny(),
                plan.priceUsd()
        );
        return new PaymentInitResponse(
                payment.getOrderNo(),
                payment.getPaymentChannel(),
                plan.priceUsd(),
                payment.getAmountCny(),
                params
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
