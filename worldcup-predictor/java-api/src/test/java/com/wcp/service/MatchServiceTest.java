package com.wcp.service;

import static org.assertj.core.api.Assertions.assertThat;

import com.wcp.dto.response.MatchSummaryResponse;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;

/**
 * `MatchService.toMatchSummary` is the boundary mapper that flattens
 * three different ml-api shapes into one DTO. Every field-type bug in
 * here ships silently — the JSON parses, the HTTP request returns 200,
 * and a frontend feature just goes blank. The `oddsAnalysis: Map → null`
 * regression that ate paid users' value-analysis tables for weeks lived
 * in this method.
 */
class MatchServiceTest {

    /** Build the minimum match dict that flows through every shape branch. */
    private static Map<String, Object> baseMatchDict() {
        Map<String, Object> m = new HashMap<>();
        m.put("match_id", 1560);
        m.put("match_date", "2026-06-11T15:00:00Z");
        m.put("home_team", "Mexico");
        m.put("away_team", "South Africa");
        m.put("competition", "WC2026");
        m.put("status", "scheduled");
        m.put("prob_home_win", 0.62);
        m.put("prob_draw", 0.22);
        m.put("prob_away_win", 0.16);
        m.put("confidence_score", 75);
        m.put("confidence_level", "high");
        return m;
    }

    @Nested
    @DisplayName("Shape: GET /matches/{id} — flat keys with team_stats / h2h / odds_analysis")
    class FlatShape {

        @Test
        @DisplayName("oddsAnalysis (List<Map>) is preserved end-to-end")
        void oddsAnalysisListSurvives() {
            // The whole point of this test: regression-pin the bug we just
            // fixed. ml-api ships odds_analysis as a *list*, not a map. If
            // the cast in toMatchSummary ever drifts back to `instanceof
            // Map`, this assertion blows up.
            Map<String, Object> raw = baseMatchDict();
            raw.put("odds_analysis", List.of(
                    Map.of("market_type", "1x2", "outcome", "home",
                            "model_prob", 0.62, "best_odds", 1.85, "ev", 0.147),
                    Map.of("market_type", "1x2", "outcome", "draw",
                            "model_prob", 0.22, "best_odds", 3.50, "ev", -0.07)
            ));

            MatchSummaryResponse out = MatchService.toMatchSummary(raw);

            assertThat(out.oddsAnalysis()).hasSize(2);
            assertThat(out.oddsAnalysis().get(0))
                    .containsEntry("market_type", "1x2")
                    .containsEntry("outcome", "home");
            assertThat(out.oddsAnalysis().get(1))
                    .containsEntry("outcome", "draw");
        }

        @Test
        @DisplayName("oddsAnalysis (non-list, e.g. accidental Map) collapses to null instead of throwing")
        void oddsAnalysisWrongTypeIsTolerated() {
            // Defensive: if some upstream regression starts emitting a Map
            // here we'd rather render an empty paywall than hard-crash.
            Map<String, Object> raw = baseMatchDict();
            raw.put("odds_analysis", Map.of("oops", "wrong-shape"));

            MatchSummaryResponse out = MatchService.toMatchSummary(raw);

            assertThat(out.oddsAnalysis()).isNull();
        }

        @Test
        @DisplayName("score_matrix passes through as-is (10×10 list of lists)")
        void scoreMatrixListPassthrough() {
            List<List<Double>> matrix = List.of(
                    List.of(0.05, 0.04, 0.02),
                    List.of(0.04, 0.06, 0.03),
                    List.of(0.02, 0.04, 0.05)
            );
            Map<String, Object> raw = baseMatchDict();
            raw.put("score_matrix", matrix);

            MatchSummaryResponse out = MatchService.toMatchSummary(raw);

            assertThat(out.scoreMatrix()).isInstanceOf(List.class);
            @SuppressWarnings("unchecked")
            List<List<Double>> back = (List<List<Double>>) out.scoreMatrix();
            assertThat(back).hasSize(3);
            assertThat(back.get(0)).hasSize(3);
        }

        @Test
        @DisplayName("over_under_probs preserved as map keyed by threshold")
        void overUnderMapPreserved() {
            Map<String, Object> raw = baseMatchDict();
            raw.put("over_under_probs", Map.of(
                    "1.5", Map.of("over", 0.73, "under", 0.27),
                    "2.5", Map.of("over", 0.48, "under", 0.52),
                    "3.5", Map.of("over", 0.27, "under", 0.73)
            ));

            MatchSummaryResponse out = MatchService.toMatchSummary(raw);

            assertThat(out.overUnderProbs()).containsKeys("1.5", "2.5", "3.5");
        }
    }

    @Nested
    @DisplayName("Shape: POST /predict — `predictions` sub-object, team objects {id,name}")
    class NestedPredictionsShape {

        @Test
        @DisplayName("probs are read from raw.predictions when nested")
        void nestedPredictionsAreUnwrapped() {
            Map<String, Object> raw = new HashMap<>();
            raw.put("match_id", 1);
            raw.put("home_team", Map.of("id", 10, "name", "Brazil", "name_zh", "巴西"));
            raw.put("away_team", Map.of("id", 11, "name", "Croatia"));
            raw.put("predictions", Map.of(
                    "prob_home_win", 0.55, "prob_draw", 0.25, "prob_away_win", 0.20,
                    "score_matrix", List.of(List.of(0.06))
            ));

            MatchSummaryResponse out = MatchService.toMatchSummary(raw);

            assertThat(out.probHomeWin()).isEqualTo(0.55);
            assertThat(out.probDraw()).isEqualTo(0.25);
            assertThat(out.scoreMatrix()).isNotNull();
            // Team object → name extracted.
            assertThat(out.homeTeam()).isEqualTo("Brazil");
            assertThat(out.awayTeam()).isEqualTo("Croatia");
        }

        @Test
        @DisplayName("status defaults to 'scheduled' when absent (POST /predict has no status)")
        void statusDefaultsToScheduled() {
            Map<String, Object> raw = new HashMap<>();
            raw.put("match_id", 1);
            raw.put("home_team", "A");
            raw.put("away_team", "B");
            raw.put("predictions", Map.of("prob_home_win", 0.5,
                    "prob_draw", 0.3, "prob_away_win", 0.2));

            MatchSummaryResponse out = MatchService.toMatchSummary(raw);

            assertThat(out.status()).isEqualTo("scheduled");
        }
    }

    @Nested
    @DisplayName("Shape: GET /predictions/today — flat with topSignalLevel")
    class TodayShape {

        @Test
        @DisplayName("hasValueSignal derived from topSignalLevel when only the level is present")
        void deriveHasValueFromLevel() {
            Map<String, Object> raw = baseMatchDict();
            raw.put("top_signal_level", 2);
            // No has_value_signal field at all.

            MatchSummaryResponse out = MatchService.toMatchSummary(raw);

            assertThat(out.topSignalLevel()).isEqualTo(2);
            assertThat(out.hasValueSignal()).isTrue();
        }

        @Test
        @DisplayName("hasValueSignal preserved verbatim when the upstream supplies it")
        void hasValueSignalRespected() {
            Map<String, Object> raw = baseMatchDict();
            raw.put("has_value_signal", false);
            raw.put("top_signal_level", 3);

            MatchSummaryResponse out = MatchService.toMatchSummary(raw);

            assertThat(out.hasValueSignal()).isFalse();
            assertThat(out.topSignalLevel()).isEqualTo(3);
        }

        @Test
        @DisplayName("topSignalLevel null → hasValueSignal null (vs false) — keeps SSR/CSR consistent")
        void nullSignalLevelStaysNull() {
            Map<String, Object> raw = baseMatchDict();
            // No signal fields at all.

            MatchSummaryResponse out = MatchService.toMatchSummary(raw);

            assertThat(out.topSignalLevel()).isNull();
            assertThat(out.hasValueSignal()).isNull();
        }
    }

    @Nested
    @DisplayName("asTeamName edge cases")
    class TeamNameMapping {

        @Test
        @DisplayName("plain string passes through")
        void stringPasses() {
            Map<String, Object> raw = baseMatchDict();
            raw.put("home_team", "Argentina");
            assertThat(MatchService.toMatchSummary(raw).homeTeam()).isEqualTo("Argentina");
        }

        @Test
        @DisplayName("garbage shape (number) falls back to '?' instead of NPE")
        void garbageFallsBackQuestionMark() {
            Map<String, Object> raw = baseMatchDict();
            raw.put("home_team", 42);
            assertThat(MatchService.toMatchSummary(raw).homeTeam()).isEqualTo("?");
        }

        @Test
        @DisplayName("Map without `name` key falls back to '?'")
        void mapWithoutNameFallback() {
            Map<String, Object> raw = baseMatchDict();
            raw.put("home_team", Map.of("id", 1));
            assertThat(MatchService.toMatchSummary(raw).homeTeam()).isEqualTo("?");
        }
    }

    @Nested
    @DisplayName("Numeric coercion")
    class NumericCoercion {

        @Test
        @DisplayName("ints / longs / doubles all pass through asLong / asInteger / asDouble")
        void mixedNumericTypes() {
            Map<String, Object> raw = baseMatchDict();
            raw.put("match_id", 99L);          // long
            raw.put("confidence_score", 80);   // int
            raw.put("home_score", 2L);         // long where Integer is expected

            MatchSummaryResponse out = MatchService.toMatchSummary(raw);
            assertThat(out.matchId()).isEqualTo(99L);
            assertThat(out.confidenceScore()).isEqualTo(80);
            assertThat(out.homeScore()).isEqualTo(2);
        }

        @Test
        @DisplayName("absent or non-numeric fields stay null instead of crashing")
        void missingFieldsStayNull() {
            Map<String, Object> raw = baseMatchDict();
            raw.remove("confidence_score");
            raw.put("home_score", "two");  // wrong type

            MatchSummaryResponse out = MatchService.toMatchSummary(raw);
            assertThat(out.confidenceScore()).isNull();
            assertThat(out.homeScore()).isNull();
        }
    }
}
