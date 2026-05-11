package com.wcp.service;

import static org.assertj.core.api.Assertions.assertThat;

import com.wcp.dto.response.MatchSummaryResponse;
import com.wcp.model.enums.SubscriptionTier;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

/**
 * Tier-gating is the chokepoint that decides which fields a paying user
 * sees vs which collapse to null for free users. Bugs here are silent and
 * billing-impacting (a paid user paying for content they can't see) — the
 * `oddsAnalysis Map → List` regression that sat in production for weeks
 * was exactly this kind of thing. These tests pin the matrix.
 */
class ContentTierServiceTest {

    private ContentTierService service;

    @BeforeEach
    void setUp() {
        service = new ContentTierService();
    }

    /** Convenience builder for the long-arg-list MatchSummaryResponse record. */
    private static MatchSummaryResponse fullPayload() {
        List<Map<String, Object>> oddsRows = List.of(
                Map.of("market_type", "1x2", "outcome", "home", "ev", 0.16)
        );
        Object scoreMatrix = List.of(List.of(0.05, 0.04), List.of(0.03, 0.02));
        Map<String, Object> overUnder = Map.of(
                "2.5", Map.of("over", 0.55, "under", 0.45)
        );
        return new MatchSummaryResponse(
                42L,
                Instant.parse("2026-06-11T15:00:00Z"),
                "Mexico", "South Africa",
                "WC2026", "scheduled",
                0.62, 0.22, 0.16,
                75, "high",
                true, 2,
                oddsRows, scoreMatrix, overUnder,
                false,
                List.of(Map.of("label", "win-rate")),
                Map.of("totalMatches", 3),
                "Estadio Azteca", "group",
                null, null, null,
                null, null, null, null
        );
    }

    @Nested
    @DisplayName("FREE tier")
    class FreeTier {

        @Test
        @DisplayName("strips score matrix, odds, over/under and signal level")
        void stripsAllPaidFields() {
            MatchSummaryResponse out = service.applyTier(fullPayload(), SubscriptionTier.FREE);

            // 1x2 probabilities + confidence are visible at every tier.
            assertThat(out.probHomeWin()).isEqualTo(0.62);
            assertThat(out.confidenceScore()).isEqualTo(75);

            // Paid columns must collapse.
            assertThat(out.oddsAnalysis()).isNull();
            assertThat(out.scoreMatrix()).isNull();
            assertThat(out.overUnderProbs()).isNull();

            // Signal level becomes a plain "any signal" boolean — free users
            // see "there is some value" but never how much.
            assertThat(out.topSignalLevel()).isNull();
            assertThat(out.hasValueSignal()).isTrue();

            // The wire flag the client uses to decide whether to show the
            // paywall overlay must be true.
            assertThat(out.locked()).isTrue();

            // Form / H2H / venue stay visible for SEO + page completeness.
            assertThat(out.teamStats()).hasSize(1);
            assertThat(out.h2h()).isNotNull();
            assertThat(out.venue()).isEqualTo("Estadio Azteca");
        }

        @Test
        @DisplayName("hasValueSignal stays null when topSignalLevel is null")
        void nullSignalStaysNull() {
            MatchSummaryResponse base = new MatchSummaryResponse(
                    1L, Instant.now(), "A", "B", "WC", "scheduled",
                    0.5, 0.3, 0.2, 60, "medium",
                    null, null,  // hasValueSignal + topSignalLevel both null
                    null, null, null, false,
                    null, null, null, null, null, null, null, null, null, null, null
            );
            MatchSummaryResponse out = service.applyTier(base, SubscriptionTier.FREE);
            assertThat(out.hasValueSignal()).isNull();
            assertThat(out.topSignalLevel()).isNull();
        }
    }

    @Nested
    @DisplayName("BASIC tier")
    class BasicTier {

        @Test
        @DisplayName("unlocks score matrix, odds, over/under, exact signal level")
        void unlocksPaidFields() {
            MatchSummaryResponse out = service.applyTier(fullPayload(), SubscriptionTier.BASIC);

            assertThat(out.oddsAnalysis()).hasSize(1);
            assertThat(out.scoreMatrix()).isNotNull();
            assertThat(out.overUnderProbs()).containsKey("2.5");
            assertThat(out.topSignalLevel()).isEqualTo(2);
            assertThat(out.hasValueSignal()).isTrue();
            assertThat(out.locked()).isFalse();
        }
    }

    @Nested
    @DisplayName("PREMIUM tier")
    class PremiumTier {

        @Test
        @DisplayName("returns the same paid fields as BASIC and unlocks premium-only flag")
        void unlocksPremiumPanels() {
            MatchSummaryResponse out = service.applyTier(fullPayload(), SubscriptionTier.PREMIUM);
            assertThat(out.oddsAnalysis()).hasSize(1);
            assertThat(out.scoreMatrix()).isNotNull();
            assertThat(out.locked()).isFalse();
            assertThat(service.canSeePremiumPanels(SubscriptionTier.PREMIUM)).isTrue();
            assertThat(service.canSeePremiumPanels(SubscriptionTier.BASIC)).isFalse();
            assertThat(service.canSeePremiumPanels(SubscriptionTier.FREE)).isFalse();
        }
    }

    @Nested
    @DisplayName("filterDetail (generic dict shape)")
    class FilterDetail {

        @Test
        @DisplayName("free user keeps only ALWAYS_VISIBLE keys")
        void freeUserStrippedToVisibleSet() {
            // Map.of caps at 10 pairs — use ofEntries for the wider payload.
            Map<String, Object> raw = Map.ofEntries(
                    Map.entry("match_id", 1),
                    Map.entry("home_team", "A"),
                    Map.entry("away_team", "B"),
                    Map.entry("competition", "WC"),
                    Map.entry("status", "scheduled"),
                    Map.entry("prob_home_win", 0.5),
                    Map.entry("prob_draw", 0.3),
                    Map.entry("prob_away_win", 0.2),
                    Map.entry("confidence_score", 60),
                    Map.entry("confidence_level", "medium"),
                    Map.entry("score_matrix", List.of()),
                    Map.entry("odds_analysis", List.of())
            );
            Map<String, Object> out = service.filterDetail(raw, SubscriptionTier.FREE);
            assertThat(out).containsKeys("match_id", "home_team", "competition");
            assertThat(out).doesNotContainKeys("score_matrix", "odds_analysis");
        }

        @Test
        @DisplayName("basic user keeps everything except premium-only panels")
        void basicUserStripsPremiumPanels() {
            Map<String, Object> raw = Map.of(
                    "match_id", 1,
                    "score_matrix", "matrix-data",
                    "xg_panel", "premium-only-xg",
                    "injuries_panel", "premium-only-injuries",
                    "confidence_filter", "premium-only-filter"
            );
            Map<String, Object> out = service.filterDetail(raw, SubscriptionTier.BASIC);
            assertThat(out).containsKey("score_matrix");
            assertThat(out).doesNotContainKeys("xg_panel", "injuries_panel", "confidence_filter");
        }

        @Test
        @DisplayName("premium user keeps everything")
        void premiumKeepsEverything() {
            Map<String, Object> raw = Map.of(
                    "score_matrix", "x", "xg_panel", "y", "injuries_panel", "z"
            );
            Map<String, Object> out = service.filterDetail(raw, SubscriptionTier.PREMIUM);
            assertThat(out).hasSize(3);
        }

        @Test
        @DisplayName("null payload normalises to empty map, not NPE")
        void nullPayloadSafe() {
            assertThat(service.filterDetail(null, SubscriptionTier.PREMIUM)).isEmpty();
        }
    }
}
