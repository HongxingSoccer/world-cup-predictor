package com.wcp.hedge;

import com.wcp.client.MlApiClient;
import com.wcp.exception.ApiException;
import com.wcp.exception.MlApiUnavailableException;
import com.wcp.hedge.dto.CreateScenarioRequest;
import com.wcp.hedge.dto.HedgeHistoryResponse;
import com.wcp.hedge.dto.HedgeStatsResponse;
import com.wcp.hedge.dto.RecalcResponse;
import com.wcp.hedge.dto.ScenarioResponse;
import com.wcp.hedge.entity.HedgeCalculationEntity;
import com.wcp.hedge.entity.HedgeResultEntity;
import com.wcp.hedge.entity.HedgeScenarioEntity;
import com.wcp.hedge.entity.ParlayLegEntity;
import com.wcp.security.UserPrincipal;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Business orchestration for M9 hedge scenarios.
 *
 * <p>Most write paths follow the same shape:
 * <ol>
 *   <li>Validate request shape against {@code scenarioType}</li>
 *   <li>Forward to ml-api (single or parlay endpoint)</li>
 *   <li>ml-api persists the canonical scenario+calculations</li>
 *   <li>Service queries them back via the {@code scenario_id} ml-api returned</li>
 *   <li>Translate to DTO</li>
 * </ol>
 *
 * <p>Reads ({@code list}, {@code detail}, {@code results}, {@code stats})
 * are pure JPA queries scoped to the calling user.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class HedgeService {

    /**
     * Canonical disclaimer; ml-api echoes the same string but we keep a
     * Java-side copy so the user never sees a different wording even if
     * ml-api is temporarily down.
     */
    public static final String HEDGE_DISCLAIMER =
            "本平台仅提供数据分析参考,不构成任何投注建议。"
            + "对冲计算器为数学工具,计算结果仅供参考,请用户自行判断。";

    private final HedgeScenarioRepository scenarioRepo;
    private final HedgeCalculationRepository calculationRepo;
    private final HedgeResultRepository resultRepo;
    private final MlApiClient mlApiClient;

    // ------------------------------------------------------------------
    // Write paths
    // ------------------------------------------------------------------

    @Transactional
    public ScenarioResponse createScenario(UserPrincipal principal, CreateScenarioRequest req) {
        if (principal == null || principal.id() == null) {
            throw ApiException.unauthorized("login required");
        }
        validateRequest(req);

        Map<String, Object> mlRequest = toMlRequest(principal.id(), req);
        Map<String, Object> mlResponse;
        if ("parlay".equals(req.scenarioType())) {
            mlResponse = mlApiClient.hedgeParlay(mlRequest);
        } else {
            mlResponse = mlApiClient.hedgeCalculate(mlRequest);
        }

        Long scenarioId = extractScenarioId(mlResponse);
        HedgeScenarioEntity scenario = scenarioRepo.findWithChildrenById(scenarioId)
                .orElseThrow(() -> new MlApiUnavailableException(
                        "scenario " + scenarioId + " not persisted by ml-api"));

        // ml-api currently writes user_id=0 (it gets the caller's identity
        // via X-API-Key only). Patch it server-side so per-user reads work.
        if (scenario.getUserId() == null || scenario.getUserId() == 0) {
            scenario = HedgeScenarioEntity.builder()
                    .id(scenario.getId())
                    .userId(principal.id())
                    .scenarioType(scenario.getScenarioType())
                    .matchId(scenario.getMatchId())
                    .originalStake(scenario.getOriginalStake())
                    .originalOdds(scenario.getOriginalOdds())
                    .originalOutcome(scenario.getOriginalOutcome())
                    .originalMarket(scenario.getOriginalMarket())
                    .hedgeMode(scenario.getHedgeMode())
                    .hedgeRatio(scenario.getHedgeRatio())
                    .status(scenario.getStatus())
                    .createdAt(scenario.getCreatedAt())
                    .updatedAt(scenario.getUpdatedAt())
                    .calculations(scenario.getCalculations())
                    .legs(scenario.getLegs())
                    .result(scenario.getResult())
                    .build();
            scenarioRepo.save(scenario);
        }

        return toDto(scenario);
    }

    @Transactional
    public RecalcResponse recalculate(UserPrincipal principal, Long scenarioId) {
        HedgeScenarioEntity scenario = mustOwn(principal, scenarioId);
        int oldCount = calculationRepo.findByScenarioIdOrderByIdAsc(scenarioId).size();

        // Strip stale calculations before re-forwarding to ml-api. ml-api
        // re-inserts a fresh row per outcome via the same code path used at
        // scenario creation.
        calculationRepo.deleteByScenarioId(scenarioId);
        calculationRepo.flush();

        Map<String, Object> mlRequest = toMlRequestFromEntity(scenario);
        Map<String, Object> mlResponse;
        if ("parlay".equals(scenario.getScenarioType())) {
            mlResponse = mlApiClient.hedgeParlay(mlRequest);
        } else {
            mlResponse = mlApiClient.hedgeCalculate(mlRequest);
        }
        // ml-api creates a new scenario row each call; we want to keep the
        // existing scenario instead, so port the new calculations onto it.
        Long newScenarioId = extractScenarioId(mlResponse);
        if (!newScenarioId.equals(scenarioId)) {
            List<HedgeCalculationEntity> moved = new ArrayList<>(
                    calculationRepo.findByScenarioIdOrderByIdAsc(newScenarioId));
            for (HedgeCalculationEntity calc : moved) {
                HedgeCalculationEntity rebound = HedgeCalculationEntity.builder()
                        .id(calc.getId())
                        .scenario(scenario)
                        .hedgeOutcome(calc.getHedgeOutcome())
                        .hedgeOdds(calc.getHedgeOdds())
                        .hedgeBookmaker(calc.getHedgeBookmaker())
                        .hedgeStake(calc.getHedgeStake())
                        .profitIfOriginalWins(calc.getProfitIfOriginalWins())
                        .profitIfHedgeWins(calc.getProfitIfHedgeWins())
                        .maxLoss(calc.getMaxLoss())
                        .guaranteedProfit(calc.getGuaranteedProfit())
                        .evOfHedge(calc.getEvOfHedge())
                        .modelProbHedge(calc.getModelProbHedge())
                        .modelAssessment(calc.getModelAssessment())
                        .calculatedAt(calc.getCalculatedAt())
                        .build();
                calculationRepo.save(rebound);
            }
            // Drop the spurious scenario row ml-api created.
            scenarioRepo.deleteById(newScenarioId);
        }

        List<HedgeCalculationEntity> fresh =
                calculationRepo.findByScenarioIdOrderByIdAsc(scenarioId);
        List<ScenarioResponse.CalculationDto> dtos = fresh.stream()
                .map(ScenarioResponse.CalculationDto::from)
                .toList();

        return new RecalcResponse(scenarioId, oldCount, dtos.size(), dtos, HEDGE_DISCLAIMER);
    }

    // ------------------------------------------------------------------
    // Read paths
    // ------------------------------------------------------------------

    @Transactional(readOnly = true)
    public Page<ScenarioResponse> listScenarios(UserPrincipal principal, Pageable pageable) {
        if (principal == null || principal.id() == null) {
            throw ApiException.unauthorized("login required");
        }
        return scenarioRepo
                .findByUserIdOrderByCreatedAtDesc(principal.id(), pageable)
                .map(this::toDto);
    }

    @Transactional(readOnly = true)
    public ScenarioResponse getScenario(UserPrincipal principal, Long scenarioId) {
        HedgeScenarioEntity scenario = mustOwn(principal, scenarioId);
        // Eager fetch children separately since the lookup above goes by user_id.
        HedgeScenarioEntity full = scenarioRepo.findWithChildrenById(scenarioId)
                .orElse(scenario);
        return toDto(full);
    }

    @Transactional(readOnly = true)
    public HedgeHistoryResponse listResults(UserPrincipal principal) {
        if (principal == null || principal.id() == null) {
            throw ApiException.unauthorized("login required");
        }
        List<HedgeResultEntity> results = resultRepo.findByUserId(principal.id());
        return new HedgeHistoryResponse(
                results.stream().map(HedgeHistoryResponse.Item::from).toList());
    }

    @Transactional(readOnly = true)
    public HedgeStatsResponse stats(UserPrincipal principal) {
        if (principal == null || principal.id() == null) {
            throw ApiException.unauthorized("login required");
        }
        Object[] agg = resultRepo.aggregateForUser(principal.id());
        // JPA returns an Object[] whose entries are typed per the SELECT.
        long total = agg[0] == null ? 0L : ((Number) agg[0]).longValue();
        BigDecimal totalPnl = (BigDecimal) (agg[1] == null ? BigDecimal.ZERO : agg[1]);
        BigDecimal wouldHave = (BigDecimal) (agg[2] == null ? BigDecimal.ZERO : agg[2]);
        BigDecimal valueAdded = (BigDecimal) (agg[3] == null ? BigDecimal.ZERO : agg[3]);
        long winning = agg[4] == null ? 0L : ((Number) agg[4]).longValue();

        BigDecimal winRatePct;
        BigDecimal roiPct;
        if (total == 0L) {
            winRatePct = BigDecimal.ZERO.setScale(2);
            roiPct = BigDecimal.ZERO.setScale(2);
        } else {
            winRatePct = new BigDecimal(winning)
                    .multiply(new BigDecimal(100))
                    .divide(new BigDecimal(total), 2, RoundingMode.HALF_UP);
            // ROI = totalPnl / total_invested * 100. We approximate
            // total_invested as the sum of |originalPnl| + |hedgePnl| floors —
            // not perfect; design §11.8 marks ROI as "建议" so an approximation
            // is acceptable here. Replace with a precise calc once the
            // settlement job records `total_staked` per row.
            BigDecimal absStakeProxy = totalPnl.abs().max(new BigDecimal("1"));
            roiPct = totalPnl
                    .multiply(new BigDecimal(100))
                    .divide(absStakeProxy, 2, RoundingMode.HALF_UP);
        }

        return new HedgeStatsResponse(
                total, winning, totalPnl, wouldHave, valueAdded, winRatePct, roiPct);
    }

    // ------------------------------------------------------------------
    // Internal helpers
    // ------------------------------------------------------------------

    private HedgeScenarioEntity mustOwn(UserPrincipal principal, Long scenarioId) {
        if (principal == null || principal.id() == null) {
            throw ApiException.unauthorized("login required");
        }
        return scenarioRepo
                .findByIdAndUserId(scenarioId, principal.id())
                .orElseThrow(() -> ApiException.notFound("hedge scenario " + scenarioId));
    }

    private void validateRequest(CreateScenarioRequest req) {
        if ("parlay".equals(req.scenarioType())) {
            if (req.legs() == null || req.legs().size() < 2) {
                throw ApiException.badRequest("parlay scenario requires at least 2 legs");
            }
            long unsettled = req.legs().stream().filter(l -> !l.isSettled()).count();
            if (unsettled != 1) {
                throw ApiException.badRequest(
                        "parlay scenario requires exactly one unsettled leg; got " + unsettled);
            }
        } else if ("single".equals(req.scenarioType())) {
            if (req.matchId() == null) {
                throw ApiException.badRequest("single scenario requires matchId");
            }
            if (req.originalOdds() == null) {
                throw ApiException.badRequest("single scenario requires originalOdds");
            }
            if (req.originalOutcome() == null || req.originalMarket() == null) {
                throw ApiException.badRequest(
                        "single scenario requires originalOutcome and originalMarket");
            }
        } else {
            throw ApiException.badRequest(
                    "unsupported scenarioType: " + req.scenarioType());
        }
    }

    private Map<String, Object> toMlRequest(Long userId, CreateScenarioRequest req) {
        Map<String, Object> body = new HashMap<>();
        if ("parlay".equals(req.scenarioType())) {
            body.put("original_stake", req.originalStake());
            body.put("hedge_mode", req.hedgeMode());
            if (req.hedgeRatio() != null) {
                body.put("hedge_ratio", req.hedgeRatio());
            }
            List<Map<String, Object>> legs = new ArrayList<>();
            for (CreateScenarioRequest.ParlayLegInput leg : req.legs()) {
                Map<String, Object> l = new HashMap<>();
                l.put("match_id", leg.matchId());
                l.put("outcome", leg.outcome());
                l.put("odds", leg.odds());
                l.put("is_settled", leg.isSettled());
                if (leg.isWon() != null) {
                    l.put("is_won", leg.isWon());
                }
                legs.add(l);
            }
            body.put("legs", legs);
        } else {
            body.put("match_id", req.matchId());
            body.put("original_stake", req.originalStake());
            body.put("original_odds", req.originalOdds());
            body.put("original_outcome", req.originalOutcome());
            body.put("original_market", req.originalMarket());
            body.put("hedge_mode", req.hedgeMode());
            if (req.hedgeRatio() != null) {
                body.put("hedge_ratio", req.hedgeRatio());
            }
        }
        // user_id passthrough is implicit via X-API-Key today; ml-api persists 0
        // and we patch it server-side. Pass it here so future ml-api versions
        // that honour it just work.
        body.put("user_id", userId);
        return body;
    }

    private Map<String, Object> toMlRequestFromEntity(HedgeScenarioEntity scenario) {
        Map<String, Object> body = new HashMap<>();
        body.put("user_id", scenario.getUserId());
        if ("parlay".equals(scenario.getScenarioType())) {
            body.put("original_stake", scenario.getOriginalStake());
            body.put("hedge_mode", scenario.getHedgeMode());
            body.put("hedge_ratio", scenario.getHedgeRatio());
            List<Map<String, Object>> legs = new ArrayList<>();
            for (ParlayLegEntity leg : scenario.getLegs()) {
                Map<String, Object> l = new HashMap<>();
                l.put("match_id", leg.getMatchId());
                l.put("outcome", leg.getOutcome());
                l.put("odds", leg.getOdds());
                l.put("is_settled", leg.getIsSettled());
                if (leg.getIsWon() != null) {
                    l.put("is_won", leg.getIsWon());
                }
                legs.add(l);
            }
            body.put("legs", legs);
        } else {
            body.put("match_id", scenario.getMatchId());
            body.put("original_stake", scenario.getOriginalStake());
            body.put("original_odds", scenario.getOriginalOdds());
            body.put("original_outcome", scenario.getOriginalOutcome());
            body.put("original_market", scenario.getOriginalMarket());
            body.put("hedge_mode", scenario.getHedgeMode());
            body.put("hedge_ratio", scenario.getHedgeRatio());
        }
        return body;
    }

    private static Long extractScenarioId(Map<String, Object> mlResponse) {
        Object raw = mlResponse.get("scenario_id");
        if (raw == null) {
            throw new MlApiUnavailableException("ml-api response missing scenario_id");
        }
        return ((Number) raw).longValue();
    }

    private ScenarioResponse toDto(HedgeScenarioEntity s) {
        List<ScenarioResponse.CalculationDto> calcs = s.getCalculations().stream()
                .map(ScenarioResponse.CalculationDto::from)
                .toList();
        List<ScenarioResponse.LegDto> legs = s.getLegs().stream()
                .map(ScenarioResponse.LegDto::from)
                .toList();
        return ScenarioResponse.from(s, calcs, legs, HEDGE_DISCLAIMER);
    }
}
