package com.wcp.service;

import com.wcp.dto.request.CreateSubscriptionRequest;
import com.wcp.dto.response.PaymentInitResponse;
import com.wcp.dto.response.SubscriptionPlanResponse;
import com.wcp.exception.ApiException;
import com.wcp.model.Payment;
import com.wcp.model.Subscription;
import com.wcp.model.User;
import com.wcp.repository.PaymentRepository;
import com.wcp.repository.SubscriptionRepository;
import com.wcp.repository.UserRepository;
import com.wcp.security.UserPrincipal;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Subscription lifecycle: catalogue, order creation, cancel/auto-renew toggles.
 *
 * <p>Pricing is hard-coded in {@link #plans()} for now. Phase 3.5 will move
 * the catalogue to a `pricing_plans` table so promo codes / regional
 * pricing land without a redeploy.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class SubscriptionService {

    private static final List<SubscriptionPlanResponse> PLAN_CATALOGUE = List.of(
            new SubscriptionPlanResponse("basic",   "monthly",       2990,  30, "Basic · Monthly"),
            new SubscriptionPlanResponse("basic",   "worldcup_pass", 6800,  60, "Basic · World-Cup Pass"),
            new SubscriptionPlanResponse("premium", "monthly",       5990,  30, "Premium · Monthly"),
            new SubscriptionPlanResponse("premium", "worldcup_pass", 12800, 60, "Premium · World-Cup Pass")
    );

    private final SubscriptionRepository subscriptionRepository;
    private final PaymentRepository paymentRepository;
    private final UserRepository userRepository;
    private final PaymentService paymentService;

    public List<SubscriptionPlanResponse> plans() {
        return PLAN_CATALOGUE;
    }

    @Transactional
    public PaymentInitResponse createSubscription(
            UserPrincipal principal, CreateSubscriptionRequest req) {
        SubscriptionPlanResponse plan = findPlan(req.tier(), req.planType());
        User user = userRepository.findByUuid(principal.uuid())
                .orElseThrow(() -> ApiException.unauthorized("user not found"));

        String orderNo = "WCP" + Instant.now().toEpochMilli() + "-" + user.getId();
        Payment payment = Payment.builder()
                .userId(user.getId())
                .orderNo(orderNo)
                .paymentChannel(req.paymentChannel())
                .amountCny(plan.priceCny())
                .status("pending")
                .build();
        payment = paymentRepository.save(payment);

        return paymentService.initPayment(payment, plan, user);
    }

    public Optional<Subscription> currentSubscription(UserPrincipal principal) {
        User user = userRepository.findByUuid(principal.uuid())
                .orElseThrow(() -> ApiException.unauthorized("user not found"));
        return subscriptionRepository.findActive(user.getId(), Instant.now());
    }

    @Transactional
    public void cancelAutoRenew(UserPrincipal principal) {
        Subscription active = currentSubscription(principal)
                .orElseThrow(() -> ApiException.notFound("active subscription"));
        if (!active.isAutoRenew()) {
            return;
        }
        active.setAutoRenew(false);
        subscriptionRepository.save(active);
    }

    /**
     * Activate the subscription window after a successful payment.
     * Called from {@link PaymentService} once the channel callback has been
     * verified, so this is the single chokepoint that mutates user tier state.
     */
    @Transactional
    public Subscription activateSubscription(Payment payment, SubscriptionPlanResponse plan, User user) {
        Instant now = Instant.now();
        Instant expires = now.plus(Duration.ofDays(plan.durationDays()));
        Subscription sub = Subscription.builder()
                .userId(user.getId())
                .tier(plan.tier())
                .planType(plan.planType())
                .status("active")
                .priceCny(plan.priceCny())
                .startedAt(now)
                .expiresAt(expires)
                .autoRenew(false)
                .paymentId(payment.getId())
                .build();
        sub = subscriptionRepository.save(sub);

        user.grantSubscription(plan.tier(), expires);
        userRepository.save(user);

        log.info(
                "subscription_activated user={} tier={} plan={} expires={}",
                user.getUuid(), plan.tier(), plan.planType(), expires
        );
        return sub;
    }

    private SubscriptionPlanResponse findPlan(String tier, String planType) {
        return PLAN_CATALOGUE.stream()
                .filter(p -> p.tier().equals(tier) && p.planType().equals(planType))
                .findFirst()
                .orElseThrow(() -> ApiException.badRequest("unknown plan: " + tier + "/" + planType));
    }
}
