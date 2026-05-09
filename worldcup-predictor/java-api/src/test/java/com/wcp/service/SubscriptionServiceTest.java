package com.wcp.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

import com.wcp.client.MlApiClient;
import com.wcp.dto.request.CreateSubscriptionRequest;
import com.wcp.dto.response.PaymentInitResponse;
import com.wcp.dto.response.SubscriptionPlanResponse;
import com.wcp.exception.ApiException;
import com.wcp.model.Payment;
import com.wcp.model.User;
import com.wcp.repository.PaymentRepository;
import com.wcp.repository.SubscriptionRepository;
import com.wcp.repository.UserRepository;
import com.wcp.security.UserPrincipal;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.Mockito;
import org.mockito.junit.jupiter.MockitoExtension;

/**
 * Pricing math + plan catalogue + Stripe vs CNY-channel routing live in
 * {@link SubscriptionService}. Two production bugs would have been caught
 * here:
 *   - findPlan referenced a non-existent CONST_NAME and broke the Java build.
 *   - CreateSubscriptionRequest's regex blocked Stripe even though the
 *     service / payment service understood it.
 */
@ExtendWith(MockitoExtension.class)
class SubscriptionServiceTest {

    @Mock private SubscriptionRepository subscriptionRepository;
    @Mock private PaymentRepository paymentRepository;
    @Mock private UserRepository userRepository;
    @Mock private PaymentService paymentService;
    @Mock private MlApiClient mlApiClient;

    @InjectMocks private SubscriptionService service;

    @BeforeEach
    void setUp() {
        // Default FX feed → live rate; lenient because the static-helper
        // tests (`usdCentsToCnyFen`, `isCnyChannel`) never invoke the FX
        // path and Mockito strict-mode would otherwise fail them.
        Mockito.lenient().when(mlApiClient.fxUsdCny()).thenReturn(7.13);
    }

    // ---------------------------------------------------------------------
    // Pure-math helpers — no mocks needed
    // ---------------------------------------------------------------------

    @Test
    @DisplayName("usdCentsToCnyFen rounds to whole fen")
    void cnyConversionRounds() {
        // 999¢ × 7.13 = 7122.87 → rounds to 7123
        assertThat(SubscriptionService.usdCentsToCnyFen(999, 7.13)).isEqualTo(7123);
        // Exact midpoint: 100 × 7.5 = 750.0
        assertThat(SubscriptionService.usdCentsToCnyFen(100, 7.5)).isEqualTo(750);
    }

    @Test
    @DisplayName("isCnyChannel — alipay + wechat are CNY, stripe is not")
    void cnyChannelClassification() {
        assertThat(SubscriptionService.isCnyChannel("alipay")).isTrue();
        assertThat(SubscriptionService.isCnyChannel("wechat_pay")).isTrue();
        assertThat(SubscriptionService.isCnyChannel("stripe")).isFalse();
        assertThat(SubscriptionService.isCnyChannel(null)).isFalse();
        assertThat(SubscriptionService.isCnyChannel("apple_pay")).isFalse();
    }

    // ---------------------------------------------------------------------
    // currentFxRate — live + fallback
    // ---------------------------------------------------------------------

    @Test
    @DisplayName("currentFxRate uses live feed when reachable")
    void liveRateUsedWhenAvailable() {
        when(mlApiClient.fxUsdCny()).thenReturn(7.215);
        assertThat(service.currentFxRate()).isEqualTo(7.215);
    }

    @Test
    @DisplayName("currentFxRate falls back to constant when feed returns 0")
    void zeroRateFallsBackToConstant() {
        when(mlApiClient.fxUsdCny()).thenReturn(0.0);
        assertThat(service.currentFxRate()).isEqualTo(SubscriptionService.FALLBACK_FX_CNY_PER_USD);
    }

    @Test
    @DisplayName("currentFxRate falls back to constant when feed returns negative")
    void negativeRateFallsBackToConstant() {
        when(mlApiClient.fxUsdCny()).thenReturn(-1.0);
        assertThat(service.currentFxRate()).isEqualTo(SubscriptionService.FALLBACK_FX_CNY_PER_USD);
    }

    // ---------------------------------------------------------------------
    // Plan catalogue
    // ---------------------------------------------------------------------

    @Test
    @DisplayName("plans() returns 4 entries — basic/premium × monthly/worldcup_pass")
    void planCatalogueShape() {
        when(mlApiClient.fxUsdCny()).thenReturn(7.20);

        List<SubscriptionPlanResponse> plans = service.plans();

        assertThat(plans).hasSize(4);
        assertThat(plans).extracting(SubscriptionPlanResponse::tier)
                .containsExactlyInAnyOrder("basic", "basic", "premium", "premium");
        assertThat(plans).extracting(SubscriptionPlanResponse::planType)
                .containsExactlyInAnyOrder(
                        "monthly", "worldcup_pass", "monthly", "worldcup_pass");
    }

    @Test
    @DisplayName("plans() prices CNY at the live FX rate, not the fallback")
    void planCnyTracksLiveFx() {
        when(mlApiClient.fxUsdCny()).thenReturn(7.13);

        SubscriptionPlanResponse basicMonthly = service.plans().stream()
                .filter(p -> p.tier().equals("basic") && p.planType().equals("monthly"))
                .findFirst()
                .orElseThrow();

        assertThat(basicMonthly.priceUsd()).isEqualTo(999);
        // 999 × 7.13 = 7122.87 → 7123 fen
        assertThat(basicMonthly.priceCny()).isEqualTo(7123);
    }

    @Test
    @DisplayName("plans() honours the fallback FX when live feed reports 0")
    void planFallbackFx() {
        when(mlApiClient.fxUsdCny()).thenReturn(0.0);

        SubscriptionPlanResponse basicMonthly = service.plans().stream()
                .filter(p -> p.tier().equals("basic") && p.planType().equals("monthly"))
                .findFirst()
                .orElseThrow();

        // 999 × 7.20 = 7192.8 → 7193 fen
        assertThat(basicMonthly.priceCny()).isEqualTo(7193);
    }

    // ---------------------------------------------------------------------
    // createSubscription — order + persistence flow
    // ---------------------------------------------------------------------

    @Test
    @DisplayName("createSubscription persists Payment with correct CNY snapshot + delegates to PaymentService")
    void createSubscriptionWritesLedger() {
        UUID userUuid = UUID.randomUUID();
        User user = User.builder()
                .id(7L)
                .uuid(userUuid)
                .email("a@b.test")
                .subscriptionTier("free")
                .locale("zh-CN")
                .timezone("Asia/Shanghai")
                .active(true)
                .role("user")
                .build();
        UserPrincipal principal = UserPrincipal.from(user);

        when(userRepository.findByUuid(userUuid)).thenReturn(Optional.of(user));
        // Echo the payment back unchanged — we don't check the JPA-assigned id
        // from the test, just that PaymentService.initPayment is invoked.
        when(paymentRepository.save(any(Payment.class))).thenAnswer(inv -> inv.getArgument(0));
        when(paymentService.initPayment(any(), any(), any())).thenReturn(
                new PaymentInitResponse("WCP-1001", "alipay", 999, 7193, java.util.Map.of())
        );

        PaymentInitResponse out = service.createSubscription(
                principal,
                new CreateSubscriptionRequest("basic", "monthly", "alipay")
        );

        assertThat(out.orderNo()).isEqualTo("WCP-1001");
        assertThat(out.paymentChannel()).isEqualTo("alipay");
        assertThat(out.amountUsd()).isEqualTo(999);
    }

    @Test
    @DisplayName("createSubscription rejects unknown plan combo with 400")
    void unknownPlanRejected() {
        UUID userUuid = UUID.randomUUID();
        User user = User.builder()
                .id(1L).uuid(userUuid).email("a@b.test")
                .subscriptionTier("free").locale("zh-CN").timezone("Asia/Shanghai")
                .active(true).role("user")
                .build();
        UserPrincipal principal = UserPrincipal.from(user);

        // findPlan throws *before* the user lookup happens for unknown plans —
        // marking lenient so strict-mode doesn't flag the unused stub.
        Mockito.lenient().when(userRepository.findByUuid(userUuid)).thenReturn(Optional.of(user));

        assertThatThrownBy(() -> service.createSubscription(
                principal,
                new CreateSubscriptionRequest("basic", "lifetime", "alipay")
        ))
                .isInstanceOf(ApiException.class)
                .hasMessageContaining("unknown plan");
    }

    @Test
    @DisplayName("createSubscription throws 401 when the user lookup fails")
    void unknownUserRejected() {
        UUID missing = UUID.randomUUID();
        User shell = User.builder()
                .id(99L).uuid(missing)
                .subscriptionTier("free").locale("zh-CN").timezone("Asia/Shanghai")
                .active(true).role("user")
                .build();
        UserPrincipal principal = UserPrincipal.from(shell);

        when(userRepository.findByUuid(missing)).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.createSubscription(
                principal,
                new CreateSubscriptionRequest("basic", "monthly", "alipay")
        ))
                .isInstanceOf(ApiException.class)
                .extracting(ex -> ((ApiException) ex).getStatus().value())
                .isEqualTo(401);
    }

    // ---------------------------------------------------------------------
    // activateSubscription — granted tier + window
    // ---------------------------------------------------------------------

    @Test
    @DisplayName("activateSubscription writes the access window onto the user")
    void activationGrantsTierAndExpiry() {
        User user = User.builder()
                .id(5L).uuid(UUID.randomUUID()).email("a@b.test")
                .subscriptionTier("free").locale("zh-CN").timezone("Asia/Shanghai")
                .active(true).role("user")
                .build();
        Payment payment = Payment.builder()
                .id(123L).userId(5L).orderNo("WCP-123")
                .amountCny(7193).status("paid")
                .build();
        SubscriptionPlanResponse plan = new SubscriptionPlanResponse(
                "premium", "monthly", 1999, 14393, 30, "Premium · Monthly"
        );

        when(subscriptionRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));

        var sub = service.activateSubscription(payment, plan, user);

        assertThat(sub.getTier()).isEqualTo("premium");
        assertThat(sub.getPlanType()).isEqualTo("monthly");
        assertThat(sub.getStatus()).isEqualTo("active");
        assertThat(sub.getExpiresAt()).isAfter(Instant.now());
        // The user object itself should now reflect the granted tier so
        // subsequent JWTs encode the right claim.
        assertThat(user.getSubscriptionTier()).isEqualTo("premium");
        assertThat(user.getSubscriptionExpires()).isAfter(Instant.now());
    }
}
