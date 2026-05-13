package com.wcp.hedge.dto;

import com.wcp.hedge.entity.HedgeResultEntity;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;

/** Settled-scenario history shape for {@code GET /api/v1/hedge/results}. */
public record HedgeHistoryResponse(List<Item> items) {

    public record Item(
            Long scenarioId,
            String scenarioType,
            Long matchId,
            String actualOutcome,
            BigDecimal originalPnl,
            BigDecimal hedgePnl,
            BigDecimal totalPnl,
            BigDecimal wouldHavePnl,
            BigDecimal hedgeValueAdded,
            OffsetDateTime settledAt
    ) {
        public static Item from(HedgeResultEntity r) {
            return new Item(
                    r.getScenario().getId(),
                    r.getScenario().getScenarioType(),
                    r.getScenario().getMatchId(),
                    r.getActualOutcome(),
                    r.getOriginalPnl(),
                    r.getHedgePnl(),
                    r.getTotalPnl(),
                    r.getWouldHavePnl(),
                    r.getHedgeValueAdded(),
                    r.getSettledAt());
        }
    }
}
