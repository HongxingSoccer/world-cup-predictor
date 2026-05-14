package com.wcp.arbitrage.dto;

import com.fasterxml.jackson.databind.JsonNode;
import com.wcp.arbitrage.entity.ArbWatchlistEntity;
import java.math.BigDecimal;
import java.time.OffsetDateTime;

public record WatchlistResponse(
        Long id,
        Long userId,
        Long competitionId,
        JsonNode marketTypes,
        BigDecimal minProfitMargin,
        boolean notifyEnabled,
        OffsetDateTime createdAt
) {
    public static WatchlistResponse from(ArbWatchlistEntity e) {
        return new WatchlistResponse(
                e.getId(),
                e.getUserId(),
                e.getCompetitionId(),
                e.getMarketTypes(),
                e.getMinProfitMargin(),
                e.isNotifyEnabled(),
                e.getCreatedAt());
    }
}
