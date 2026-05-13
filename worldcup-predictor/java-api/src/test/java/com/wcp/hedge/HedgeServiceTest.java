package com.wcp.hedge;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.wcp.client.MlApiClient;
import com.wcp.exception.ApiException;
import com.wcp.exception.MlApiUnavailableException;
import com.wcp.hedge.dto.CreateScenarioRequest;
import com.wcp.hedge.dto.HedgeStatsResponse;
import com.wcp.hedge.dto.ScenarioResponse;
import com.wcp.hedge.entity.HedgeCalculationEntity;
import com.wcp.hedge.entity.HedgeResultEntity;
import com.wcp.hedge.entity.HedgeScenarioEntity;
import com.wcp.model.enums.SubscriptionTier;
import com.wcp.security.UserPrincipal;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.web.client.HttpClientErrorException;

/**
 * Unit tests for {@link HedgeService}. Covers all six controller-facing
 * code paths plus the failure-mode branches.
 */
@ExtendWith(MockitoExtension.class)
class HedgeServiceTest {

    @Mock private HedgeScenarioRepository scenarioRepo;
    @Mock private HedgeCalculationRepository calculationRepo;
    @Mock private HedgeResultRepository resultRepo;
    @Mock private MlApiClient mlApiClient;

    @InjectMocks private HedgeService service;

    private UserPrincipal premiumUser;
    private UserPrincipal otherUser;

    @BeforeEach
    void setup() {
        premiumUser = new UserPrincipal(
                42L, UUID.randomUUID(), "user", SubscriptionTier.PREMIUM, true);
        otherUser = new UserPrincipal(
                99L, UUID.randomUUID(), "user", SubscriptionTier.PREMIUM, true);
    }

    // -------------------------------------------------------------------
    // createScenario
    // -------------------------------------------------------------------

    @Test
    @DisplayName("createScenario(single) forwards to /calculate and persists user_id patch")
    void createSingleScenarioSucceeds() {
        CreateScenarioRequest req = new CreateScenarioRequest(
                "single",
                123L,
                new BigDecimal("100"),
                new BigDecimal("2.10"),
                "home",
                "1x2",
                "full",
                null,
                null);
        // ml-api responds with the persisted scenario_id (1L).
        when(mlApiClient.hedgeCalculate(any())).thenReturn(Map.of("scenario_id", 1L));
        HedgeScenarioEntity persisted = newScenario(1L, /* userId */ 0L, "single");
        when(scenarioRepo.findWithChildrenById(1L)).thenReturn(Optional.of(persisted));
        when(scenarioRepo.save(any(HedgeScenarioEntity.class)))
                .thenAnswer(invocation -> invocation.getArgument(0));

        ScenarioResponse resp = service.createScenario(premiumUser, req);

        assertThat(resp.scenarioId()).isEqualTo(1L);
        assertThat(resp.disclaimer()).contains("本平台仅提供数据分析参考");
        verify(mlApiClient).hedgeCalculate(any());
        verify(mlApiClient, never()).hedgeParlay(any());
        // user_id was 0 → service patches it to the principal id.
        verify(scenarioRepo).save(any(HedgeScenarioEntity.class));
    }

    @Test
    @DisplayName("createScenario(parlay) requires legs ≥ 2 and exactly one unsettled")
    void createParlayValidatesLegs() {
        CreateScenarioRequest tooFew = new CreateScenarioRequest(
                "parlay",
                null,
                new BigDecimal("50"),
                null, null, null,
                "full", null,
                List.of(new CreateScenarioRequest.ParlayLegInput(
                        1L, "home", new BigDecimal("1.85"), false, null)));
        assertThatThrownBy(() -> service.createScenario(premiumUser, tooFew))
                .isInstanceOf(ApiException.class)
                .hasMessageContaining("at least 2 legs");

        CreateScenarioRequest allSettled = new CreateScenarioRequest(
                "parlay",
                null,
                new BigDecimal("50"),
                null, null, null,
                "full", null,
                List.of(
                        new CreateScenarioRequest.ParlayLegInput(
                                1L, "home", new BigDecimal("1.85"), true, true),
                        new CreateScenarioRequest.ParlayLegInput(
                                2L, "over", new BigDecimal("1.90"), true, true)));
        assertThatThrownBy(() -> service.createScenario(premiumUser, allSettled))
                .isInstanceOf(ApiException.class)
                .hasMessageContaining("exactly one unsettled");
    }

    @Test
    @DisplayName("createScenario routes parlay requests to /parlay endpoint")
    void createParlayCallsParlayEndpoint() {
        CreateScenarioRequest req = new CreateScenarioRequest(
                "parlay",
                null,
                new BigDecimal("50"),
                null, null, null,
                "full", null,
                List.of(
                        new CreateScenarioRequest.ParlayLegInput(
                                1L, "home", new BigDecimal("1.85"), true, true),
                        new CreateScenarioRequest.ParlayLegInput(
                                2L, "over", new BigDecimal("1.90"), true, true),
                        new CreateScenarioRequest.ParlayLegInput(
                                3L, "home", new BigDecimal("2.20"), false, null)));
        when(mlApiClient.hedgeParlay(any())).thenReturn(Map.of("scenario_id", 7L));
        HedgeScenarioEntity persisted = newScenario(7L, premiumUser.id(), "parlay");
        when(scenarioRepo.findWithChildrenById(7L)).thenReturn(Optional.of(persisted));

        service.createScenario(premiumUser, req);

        verify(mlApiClient).hedgeParlay(any());
        verify(mlApiClient, never()).hedgeCalculate(any());
    }

    @Test
    @DisplayName("createScenario without login → unauthorized")
    void createScenarioRequiresLogin() {
        CreateScenarioRequest req = new CreateScenarioRequest(
                "single", 1L, new BigDecimal("100"),
                new BigDecimal("2.10"), "home", "1x2",
                "full", null, null);
        assertThatThrownBy(() -> service.createScenario(null, req))
                .isInstanceOf(ApiException.class)
                .hasMessageContaining("login required");
    }

    @Test
    @DisplayName("createScenario unwraps ml-api 5xx as MlApiUnavailableException")
    void createScenarioMlApiDown() {
        CreateScenarioRequest req = new CreateScenarioRequest(
                "single", 1L, new BigDecimal("100"),
                new BigDecimal("2.10"), "home", "1x2",
                "full", null, null);
        when(mlApiClient.hedgeCalculate(any()))
                .thenThrow(new MlApiUnavailableException("/hedge/calculate returned 500"));

        assertThatThrownBy(() -> service.createScenario(premiumUser, req))
                .isInstanceOf(MlApiUnavailableException.class);
    }

    @Test
    @DisplayName("createScenario bubbles ml-api 4xx as HttpClientErrorException")
    void createScenarioMlApi4xx() {
        CreateScenarioRequest req = new CreateScenarioRequest(
                "single", 1L, new BigDecimal("100"),
                new BigDecimal("2.10"), "home", "1x2",
                "full", null, null);
        when(mlApiClient.hedgeCalculate(any()))
                .thenThrow(HttpClientErrorException.create(
                        org.springframework.http.HttpStatus.BAD_REQUEST,
                        "BadRequest", null, null, null));

        assertThatThrownBy(() -> service.createScenario(premiumUser, req))
                .isInstanceOf(HttpClientErrorException.class);
    }

    // -------------------------------------------------------------------
    // listScenarios + getScenario
    // -------------------------------------------------------------------

    @Test
    @DisplayName("listScenarios is scoped to the caller's user_id")
    void listScenariosScopedToUser() {
        HedgeScenarioEntity mine = newScenario(1L, premiumUser.id(), "single");
        when(scenarioRepo.findByUserIdOrderByCreatedAtDesc(
                eq(premiumUser.id()), any()))
                .thenReturn(new PageImpl<>(List.of(mine)));

        Page<ScenarioResponse> page = service.listScenarios(premiumUser, PageRequest.of(0, 20));

        assertThat(page.getContent()).hasSize(1);
        assertThat(page.getContent().get(0).scenarioId()).isEqualTo(1L);
        verify(scenarioRepo).findByUserIdOrderByCreatedAtDesc(eq(premiumUser.id()), any());
        verify(scenarioRepo, never()).findByUserIdOrderByCreatedAtDesc(
                eq(otherUser.id()), any());
    }

    @Test
    @DisplayName("getScenario refuses to surface another user's scenario")
    void getScenarioOtherUserNotFound() {
        when(scenarioRepo.findByIdAndUserId(7L, premiumUser.id()))
                .thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.getScenario(premiumUser, 7L))
                .isInstanceOf(ApiException.class)
                .hasMessageContaining("not found");
    }

    @Test
    @DisplayName("getScenario returns the full eager-loaded scenario")
    void getScenarioSuccess() {
        HedgeScenarioEntity entity = newScenario(7L, premiumUser.id(), "single");
        when(scenarioRepo.findByIdAndUserId(7L, premiumUser.id()))
                .thenReturn(Optional.of(entity));
        when(scenarioRepo.findWithChildrenById(7L)).thenReturn(Optional.of(entity));

        ScenarioResponse resp = service.getScenario(premiumUser, 7L);

        assertThat(resp.scenarioId()).isEqualTo(7L);
        assertThat(resp.scenarioType()).isEqualTo("single");
    }

    // -------------------------------------------------------------------
    // recalculate
    // -------------------------------------------------------------------

    @Test
    @DisplayName("recalculate wipes stale calculations and re-invokes ml-api")
    void recalculateRebuilds() {
        HedgeScenarioEntity entity = newScenario(7L, premiumUser.id(), "single");
        // 2 stale calcs prior to recalc.
        HedgeCalculationEntity stale1 = HedgeCalculationEntity.builder()
                .id(1L).scenario(entity).hedgeOutcome("draw")
                .hedgeOdds(new BigDecimal("3.40"))
                .hedgeBookmaker("pinnacle")
                .hedgeStake(BigDecimal.ZERO)
                .profitIfOriginalWins(BigDecimal.ZERO)
                .profitIfHedgeWins(BigDecimal.ZERO)
                .maxLoss(BigDecimal.ZERO).build();
        HedgeCalculationEntity stale2 = HedgeCalculationEntity.builder()
                .id(2L).scenario(entity).hedgeOutcome("away")
                .hedgeOdds(new BigDecimal("4.10"))
                .hedgeBookmaker("bet365")
                .hedgeStake(BigDecimal.ZERO)
                .profitIfOriginalWins(BigDecimal.ZERO)
                .profitIfHedgeWins(BigDecimal.ZERO)
                .maxLoss(BigDecimal.ZERO).build();

        when(scenarioRepo.findByIdAndUserId(7L, premiumUser.id()))
                .thenReturn(Optional.of(entity));
        when(calculationRepo.findByScenarioIdOrderByIdAsc(7L))
                .thenReturn(List.of(stale1, stale2)) // first call: count stale
                .thenReturn(List.of()); // after recalc: empty (no fresh, mocked away)
        // ml-api returns the SAME scenario id → no rebind/delete branch.
        when(mlApiClient.hedgeCalculate(any())).thenReturn(Map.of("scenario_id", 7L));

        service.recalculate(premiumUser, 7L);

        verify(calculationRepo).deleteByScenarioId(7L);
        verify(mlApiClient).hedgeCalculate(any());
    }

    @Test
    @DisplayName("recalculate(other user's scenario) → 404")
    void recalculateForbiddenForOtherUser() {
        when(scenarioRepo.findByIdAndUserId(7L, premiumUser.id()))
                .thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.recalculate(premiumUser, 7L))
                .isInstanceOf(ApiException.class)
                .hasMessageContaining("not found");
        verify(mlApiClient, never()).hedgeCalculate(any());
    }

    // -------------------------------------------------------------------
    // stats
    // -------------------------------------------------------------------

    @Test
    @DisplayName("stats aggregates totals + computes win-rate / ROI")
    void statsAggregates() {
        Object[] row = new Object[] {
                3L, // total
                new BigDecimal("150.00"), // total_pnl
                new BigDecimal("100.00"), // would_have_pnl
                new BigDecimal("50.00"), // hedge_value_added
                2L // winning
        };
        when(resultRepo.aggregateForUser(premiumUser.id())).thenReturn(row);

        HedgeStatsResponse stats = service.stats(premiumUser);

        assertThat(stats.totalSettled()).isEqualTo(3L);
        assertThat(stats.winningScenarios()).isEqualTo(2L);
        assertThat(stats.totalPnl()).isEqualByComparingTo("150.00");
        // win rate = 2/3 × 100 = 66.67
        assertThat(stats.winRatePct()).isEqualByComparingTo("66.67");
    }

    @Test
    @DisplayName("stats handles empty history without zero-division")
    void statsEmpty() {
        Object[] row = new Object[] {0L, BigDecimal.ZERO, BigDecimal.ZERO, BigDecimal.ZERO, 0L};
        when(resultRepo.aggregateForUser(premiumUser.id())).thenReturn(row);

        HedgeStatsResponse stats = service.stats(premiumUser);

        assertThat(stats.totalSettled()).isZero();
        assertThat(stats.winRatePct()).isEqualByComparingTo("0.00");
        assertThat(stats.roiPct()).isEqualByComparingTo("0.00");
    }

    @Test
    @DisplayName("listResults is scoped to the caller's user_id")
    void listResultsScopedToUser() {
        HedgeScenarioEntity sc = newScenario(1L, premiumUser.id(), "single");
        HedgeResultEntity r = HedgeResultEntity.builder()
                .id(1L).scenario(sc).actualOutcome("home")
                .originalPnl(new BigDecimal("110.00"))
                .hedgePnl(new BigDecimal("-19.38"))
                .totalPnl(new BigDecimal("90.62"))
                .wouldHavePnl(new BigDecimal("110.00"))
                .hedgeValueAdded(new BigDecimal("-19.38"))
                .settledAt(OffsetDateTime.now())
                .build();
        when(resultRepo.findByUserId(premiumUser.id())).thenReturn(List.of(r));

        assertThat(service.listResults(premiumUser).items()).hasSize(1);
        verify(resultRepo).findByUserId(premiumUser.id());
        verify(resultRepo, never()).findByUserId(otherUser.id());
    }

    // -------------------------------------------------------------------
    // helpers
    // -------------------------------------------------------------------

    private static HedgeScenarioEntity newScenario(Long id, Long userId, String type) {
        return HedgeScenarioEntity.builder()
                .id(id)
                .userId(userId)
                .scenarioType(type)
                .matchId(123L)
                .originalStake(new BigDecimal("100"))
                .originalOdds(new BigDecimal("2.10"))
                .originalOutcome("home")
                .originalMarket("1x2")
                .hedgeMode("full")
                .hedgeRatio(new BigDecimal("1.000"))
                .status("active")
                .createdAt(OffsetDateTime.now())
                .updatedAt(OffsetDateTime.now())
                .build();
    }
}
