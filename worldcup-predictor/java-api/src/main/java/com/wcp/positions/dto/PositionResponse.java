package com.wcp.positions.dto;

import com.wcp.positions.entity.PositionEntity;
import java.math.BigDecimal;
import java.time.OffsetDateTime;

public record PositionResponse(
        Long id,
        Long userId,
        Long matchId,
        String platform,
        String market,
        String outcome,
        BigDecimal stake,
        BigDecimal odds,
        OffsetDateTime placedAt,
        String status,
        String notes,
        OffsetDateTime createdAt,
        OffsetDateTime updatedAt,
        OffsetDateTime lastAlertAt,
        BigDecimal settlementPnl
) {
    public static PositionResponse from(PositionEntity e) {
        return new PositionResponse(
                e.getId(),
                e.getUserId(),
                e.getMatchId(),
                e.getPlatform(),
                e.getMarket(),
                e.getOutcome(),
                e.getStake(),
                e.getOdds(),
                e.getPlacedAt(),
                e.getStatus(),
                e.getNotes(),
                e.getCreatedAt(),
                e.getUpdatedAt(),
                e.getLastAlertAt(),
                e.getSettlementPnl());
    }
}
