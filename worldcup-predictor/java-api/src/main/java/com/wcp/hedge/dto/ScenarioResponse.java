package com.wcp.hedge.dto;

import com.wcp.hedge.entity.HedgeCalculationEntity;
import com.wcp.hedge.entity.HedgeScenarioEntity;
import com.wcp.hedge.entity.ParlayLegEntity;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;

/** Detailed response shape for {@code GET /scenarios/{id}} + the create endpoint. */
public record ScenarioResponse(
        Long scenarioId,
        String scenarioType,
        Long matchId,
        BigDecimal originalStake,
        BigDecimal originalOdds,
        String originalOutcome,
        String originalMarket,
        String hedgeMode,
        BigDecimal hedgeRatio,
        String status,
        OffsetDateTime createdAt,
        List<CalculationDto> calculations,
        List<LegDto> legs,
        String disclaimer
) {

    public record CalculationDto(
            Long id,
            String hedgeOutcome,
            BigDecimal hedgeOdds,
            String hedgeBookmaker,
            BigDecimal hedgeStake,
            BigDecimal profitIfOriginalWins,
            BigDecimal profitIfHedgeWins,
            BigDecimal maxLoss,
            BigDecimal guaranteedProfit,
            BigDecimal evOfHedge,
            BigDecimal modelProbHedge,
            String modelAssessment
    ) {
        public static CalculationDto from(HedgeCalculationEntity e) {
            return new CalculationDto(
                    e.getId(),
                    e.getHedgeOutcome(),
                    e.getHedgeOdds(),
                    e.getHedgeBookmaker(),
                    e.getHedgeStake(),
                    e.getProfitIfOriginalWins(),
                    e.getProfitIfHedgeWins(),
                    e.getMaxLoss(),
                    e.getGuaranteedProfit(),
                    e.getEvOfHedge(),
                    e.getModelProbHedge(),
                    e.getModelAssessment());
        }
    }

    public record LegDto(
            Short legOrder,
            Long matchId,
            String outcome,
            BigDecimal odds,
            Boolean isSettled,
            Boolean isWon
    ) {
        public static LegDto from(ParlayLegEntity e) {
            return new LegDto(
                    e.getLegOrder(),
                    e.getMatchId(),
                    e.getOutcome(),
                    e.getOdds(),
                    e.getIsSettled(),
                    e.getIsWon());
        }
    }

    public static ScenarioResponse from(
            HedgeScenarioEntity s,
            List<CalculationDto> calcs,
            List<LegDto> legs,
            String disclaimer) {
        return new ScenarioResponse(
                s.getId(),
                s.getScenarioType(),
                s.getMatchId(),
                s.getOriginalStake(),
                s.getOriginalOdds(),
                s.getOriginalOutcome(),
                s.getOriginalMarket(),
                s.getHedgeMode(),
                s.getHedgeRatio(),
                s.getStatus(),
                s.getCreatedAt(),
                calcs,
                legs,
                disclaimer);
    }
}
