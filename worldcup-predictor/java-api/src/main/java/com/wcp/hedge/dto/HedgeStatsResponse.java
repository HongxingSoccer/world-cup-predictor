package com.wcp.hedge.dto;

import java.math.BigDecimal;

/**
 * Aggregate stats for {@code GET /api/v1/hedge/stats}. Used by the
 * marketing dashboard + the user's personal "对冲战绩" page.
 *
 * <p>{@code roiPct} is rendered server-side to avoid float drift in the
 * frontend (BigDecimal / BigDecimal → BigDecimal, rounded to 2 dp).
 */
public record HedgeStatsResponse(
        long totalSettled,
        long winningScenarios,
        BigDecimal totalPnl,
        BigDecimal totalWouldHavePnl,
        BigDecimal totalHedgeValueAdded,
        BigDecimal winRatePct,
        BigDecimal roiPct
) {}
