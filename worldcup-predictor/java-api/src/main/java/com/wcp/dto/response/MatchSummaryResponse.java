package com.wcp.dto.response;

import java.time.Instant;
import java.util.Map;

/**
 * Tier-aware match summary. Some fields collapse to {@code null} for free
 * users (see {@link com.wcp.service.ContentTierService}); they are therefore
 * always nullable on the wire.
 */
public record MatchSummaryResponse(
        Long matchId,
        Instant matchDate,
        String homeTeam,
        String awayTeam,
        String competition,
        String status,
        Double probHomeWin,
        Double probDraw,
        Double probAwayWin,
        Integer confidenceScore,
        String confidenceLevel,
        Boolean hasValueSignal,
        Integer topSignalLevel,
        Map<String, Object> oddsAnalysis,
        Map<String, Object> scoreMatrix,
        Map<String, Object> overUnderProbs,
        Boolean locked
) {}
