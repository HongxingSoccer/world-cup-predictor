package com.wcp.service;

import com.wcp.dto.response.MatchSummaryResponse;
import com.wcp.model.enums.SubscriptionTier;
import java.util.Map;
import org.springframework.stereotype.Service;

/**
 * Tier-aware content gating.
 *
 * <p>Translates the matrix in §2.7 of the Phase-3 spec into a single applyTier
 * method: every paid field collapses to {@code null} (with {@code locked=true})
 * for free users; advanced fields (xG / injury / confidence-filter) require
 * the premium tier.
 *
 * <p>Used by {@link MatchService} after assembling the raw ML payload but
 * before the controller serialises it.
 */
@Service
public class ContentTierService {

    /** Apply gating to a match summary based on the caller's tier. */
    public MatchSummaryResponse applyTier(MatchSummaryResponse raw, SubscriptionTier tier) {
        boolean isFree = tier == SubscriptionTier.FREE;
        boolean isAtLeastBasic = tier.isAtLeast(SubscriptionTier.BASIC);

        return new MatchSummaryResponse(
                raw.matchId(),
                raw.matchDate(),
                raw.homeTeam(),
                raw.awayTeam(),
                raw.competition(),
                raw.status(),

                // 1x2 probs are visible at every tier.
                raw.probHomeWin(),
                raw.probDraw(),
                raw.probAwayWin(),

                // Confidence score is visible at every tier.
                raw.confidenceScore(),
                raw.confidenceLevel(),

                // Free users see only "is there ANY signal" — never the level.
                isFree ? hasAnySignal(raw) : raw.hasValueSignal(),
                // Free users get null for the integer level; basic+ get full info.
                isFree ? null : raw.topSignalLevel(),

                // Odds analysis full table requires basic+.
                isAtLeastBasic ? raw.oddsAnalysis() : null,

                // Top-10 score-matrix requires basic+.
                isAtLeastBasic ? raw.scoreMatrix() : null,

                // OU / handicap requires basic+.
                isAtLeastBasic ? raw.overUnderProbs() : null,

                // Mark the response as locked for clients that need a hint
                // for "show paywall here".
                !isAtLeastBasic,

                // Form / H2H / venue / score are all metadata: every tier sees them.
                raw.teamStats(),
                raw.h2h(),
                raw.venue(),
                raw.round(),
                raw.homeScore(),
                raw.awayScore(),
                raw.favorited()
        );
    }

    /** Premium-only fields (xG, injuries, confidence filter) helper. */
    public boolean canSeePremiumPanels(SubscriptionTier tier) {
        return tier == SubscriptionTier.PREMIUM;
    }

    /** Filter a generic dict-shaped detail payload by tier. */
    public Map<String, Object> filterDetail(Map<String, Object> raw, SubscriptionTier tier) {
        if (raw == null) {
            return Map.of();
        }
        if (tier.isAtLeast(SubscriptionTier.BASIC)) {
            // Basic sees everything except the premium-only deep panels.
            if (canSeePremiumPanels(tier)) {
                return raw;
            }
            // Strip premium-only keys.
            return raw.entrySet().stream()
                    .filter(e -> !PREMIUM_ONLY_KEYS.contains(e.getKey()))
                    .collect(java.util.stream.Collectors.toUnmodifiableMap(
                            Map.Entry::getKey, Map.Entry::getValue));
        }
        // Free: keep only the always-visible keys.
        return raw.entrySet().stream()
                .filter(e -> ALWAYS_VISIBLE_KEYS.contains(e.getKey()))
                .collect(java.util.stream.Collectors.toUnmodifiableMap(
                        Map.Entry::getKey, Map.Entry::getValue));
    }

    private static Boolean hasAnySignal(MatchSummaryResponse raw) {
        if (raw.topSignalLevel() == null) {
            return null;
        }
        return raw.topSignalLevel() > 0;
    }

    private static final java.util.Set<String> ALWAYS_VISIBLE_KEYS = java.util.Set.of(
            "match_id", "match_date", "home_team", "away_team", "competition", "status",
            "prob_home_win", "prob_draw", "prob_away_win", "confidence_score",
            "confidence_level"
    );

    private static final java.util.Set<String> PREMIUM_ONLY_KEYS = java.util.Set.of(
            "xg_panel", "injuries_panel", "confidence_filter"
    );
}
