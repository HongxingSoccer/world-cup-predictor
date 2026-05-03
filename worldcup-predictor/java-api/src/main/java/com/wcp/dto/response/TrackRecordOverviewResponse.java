package com.wcp.dto.response;

import java.math.BigDecimal;
import java.time.Instant;

/** One row of the public scoreboard: aggregate stat per (statType, period). */
public record TrackRecordOverviewResponse(
        String statType,
        String period,
        int totalPredictions,
        int hits,
        BigDecimal hitRate,
        BigDecimal totalPnlUnits,
        BigDecimal roi,
        int currentStreak,
        int bestStreak,
        Instant updatedAt
) {}
