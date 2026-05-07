package com.wcp.dto.response;

import java.time.Instant;
import java.util.List;
import java.util.Map;

/**
 * Tier-aware match summary. Some fields collapse to {@code null} for free
 * users (see {@link com.wcp.service.ContentTierService}); they are therefore
 * always nullable on the wire.
 *
 * {@code teamStats} + {@code h2h} are populated by the read endpoint
 * (/matches/{id}) only — list views (today / upcoming) leave them null.
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
        Object scoreMatrix,
        Map<String, Object> overUnderProbs,
        Boolean locked,
        List<Map<String, Object>> teamStats,
        Map<String, Object> h2h,
        String venue,
        String round,
        Integer homeScore,
        Integer awayScore,
        // Detail-only: true when the authenticated user has favourited this
        // match. Always null on list views and for anonymous callers.
        Boolean favorited
) {}
