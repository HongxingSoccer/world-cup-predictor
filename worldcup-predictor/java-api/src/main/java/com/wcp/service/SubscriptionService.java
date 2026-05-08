package com.wcp.service;

import com.wcp.client.MlApiClient;
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
import java.util.Set;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Subscription lifecycle: catalogue, order creation, cancel/auto-renew toggles.
 *
 * <p>Catalogue is denominated in <strong>USD</strong> (cents). CNY is
 * computed at request time using a live exchange rate fetched from
 * {@link com.wcp.client.MlApiClient#fxUsdCny()} (which proxies
 * frankfurter.app and caches for 1h). When the FX feed is unreachable
 * we fall back to {@link #FALLBACK_FX_CNY_PER_USD} so the page never
 * goes blank.
 *
 * <p>Channels:
 * <ul>
 *   <li>{@code alipay} / {@code wechat_pay} — charged in CNY at the
 *       freshly-computed rate.</li>
 *   <li>{@code stripe} (and any future {@code apple_pay} / {@code google_pay})
 *       — charged in USD natively. The Payment row stores both currencies
 *       (CNY mirrored at the order-time rate for ledger continuity).</li>
 * </ul>
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class SubscriptionService {

    /** Fallback when the FX feed is unreachable on cold start. */
    public static final double FALLBACK_FX_CNY_PER_USD = 7.20;

    /** Channels whose underlying gateway settles in CNY. */
    private static final Set<String> CNY_CHANNELS = Set.of("alipay", "wechat_pay");

    /**
     * Catalogue without the CNY column — that's filled in per-request from
     * the live FX rate so plans always show today's number.
     */
    private record CatalogueEntry(String tier, String planType, int priceUsdCents, int days, String label) {}

    private static final List<CatalogueEntry> CATALOGUE = List.of(
            new CatalogueEntry("basic",   "monthly",        999, 30, "Basic · Monthly"),
            new CatalogueEntry("basic",   "worldcup_pass", 2999, 60, "Basic · World-Cup Pass"),
            new CatalogueEntry("premium", "monthly",       1999, 30, "Premium · Monthly"),
            new CatalogueEntry("premium", "worldcup_pass", 4999, 60, "Premium · World-Cup Pass")
    );

    /** Convert USD cents → CNY fen using the supplied rate, rounded to whole fen. */
    public static int usdCentsToCnyFen(int priceUsdCents, double fxRate) {
        return (int) Math.round(priceUsdCents * fxRate);
    }

    private final SubscriptionRepository subscriptionRepository;
    private final PaymentRepository paymentRepository;
    private final UserRepository userRepository;
    private final PaymentService paymentService;
    private final MlApiClient mlApiClient;

    /** Public read of the current FX rate; falls back to the constant on failure. */
    public double currentFxRate() {
        double live = mlApiClient.fxUsdCny();
        return live > 0 ? live : FALLBACK_FX_CNY_PER_USD;
    }

    public List<SubscriptionPlanResponse> plans() {
        double fx = currentFxRate();
        return CATALOGUE.stream()
                .map(c -> new SubscriptionPlanResponse(
                        c.tier(), c.planType(), c.priceUsdCents(),
                        usdCentsToCnyFen(c.priceUsdCents(), fx),
                        c.days(), c.label()))
                .toList();
    }

    @Transactional
    public PaymentInitResponse createSubscription(
            UserPrincipal principal, CreateSubscriptionRequest req) {
        SubscriptionPlanResponse plan = findPlan(req.tier(), req.planType());
        User user = userRepository.findByUuid(principal.uuid())
                .orElseThrow(() -> ApiException.unauthorized("user not found"));

        String orderNo = "WCP" + Instant.now().toEpochMilli() + "-" + user.getId();
        // CNY for the persisted ledger is always computed at the order-time
        // rate, even for USD-native channels (Stripe etc.) — so reconciliation
        // can convert back if needed. The actual charge to the gateway,
        // however, is denominated by the channel (see PaymentService).
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

    /** True iff the channel settles in CNY (Alipay / WeChat). */
    public static boolean isCnyChannel(String channel) {
        return channel != null && CNY_CHANNELS.contains(channel);
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
        double fx = currentFxRate();
        return CATALOGUE.stream()
                .filter(c -> c.tier().equals(tier) && c.planType().equals(planType))
                .findFirst()
                .map(c -> new SubscriptionPlanResponse(
                        c.tier(), c.planType(), c.priceUsdCents(),
                        usdCentsToCnyFen(c.priceUsdCents(), fx),
                        c.days(), c.label()))
                .orElseThrow(() -> ApiException.badRequest("unknown plan: " + tier + "/" + planType));
    }
}
