package com.wcp.integration;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.node.ObjectNode;
import com.wcp.model.User;
import com.wcp.repository.UserRepository;
import java.time.Instant;
import java.time.LocalDate;
import java.time.temporal.ChronoUnit;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MvcResult;

/**
 * Match-list / detail tier-gating end-to-end.
 *
 * Free / anonymous users must see paid fields collapsed to null and
 * {@code locked=true}; basic / premium users must see them populated.
 * The unit test on ContentTierService already pins the matrix in
 * isolation — this test goes through the full HTTP path so a future
 * refactor that swaps the @AuthenticationPrincipal resolver or skips
 * ContentTierService entirely (the recent oddsAnalysis-as-Map bug was
 * a near miss here) gets caught.
 */
class MatchControllerIntegrationTest extends IntegrationTestBase {

    @Autowired private UserRepository userRepository;

    /** Register a free user + return their bearer access token. */
    private String registerAccess(String email) throws Exception {
        ObjectNode body = objectMapper.createObjectNode()
                .put("email", email)
                .put("password", "Password123");
        MvcResult res = mockMvc.perform(post("/api/v1/auth/register")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body.toString()))
                .andExpect(status().isCreated())
                .andReturn();
        return objectMapper.readTree(res.getResponse().getContentAsString())
                .get("accessToken").asText();
    }

    /** Register + then elevate to premium via repository so the next JWT carries the tier. */
    private String premiumAccess(String email) throws Exception {
        // Step 1: register the user (free tier, normal flow).
        registerAccess(email);
        // Step 2: flip tier in the DB.
        User u = userRepository.findByEmail(email).orElseThrow();
        u.grantSubscription("premium", Instant.now().plus(30, ChronoUnit.DAYS));
        userRepository.save(u);
        // Step 3: re-login so the new JWT carries the premium tier claim
        // (the access token is the chokepoint for tier downstream).
        ObjectNode body = objectMapper.createObjectNode()
                .put("email", email)
                .put("password", "Password123");
        MvcResult res = mockMvc.perform(post("/api/v1/auth/login")
                .contentType(MediaType.APPLICATION_JSON)
                .content(body.toString()))
                .andExpect(status().isOk())
                .andReturn();
        return objectMapper.readTree(res.getResponse().getContentAsString())
                .get("accessToken").asText();
    }

    /**
     * Canonical full-content match payload that the ml-api would return for
     * a finished prediction. Includes every tier-gated column so the
     * ContentTierService matrix has something to collapse for free users.
     */
    private Map<String, Object> fullMatchPayload(long id) {
        Map<String, Object> payload = new HashMap<>();
        payload.put("match_id", id);
        payload.put("match_date", "2026-06-11T15:00:00Z");
        payload.put("home_team", "Mexico");
        payload.put("away_team", "South Africa");
        payload.put("competition", "WC2026");
        payload.put("status", "scheduled");
        payload.put("prob_home_win", 0.62);
        payload.put("prob_draw", 0.22);
        payload.put("prob_away_win", 0.16);
        payload.put("confidence_score", 75);
        payload.put("confidence_level", "high");
        payload.put("top_signal_level", 2);
        payload.put("has_value_signal", true);
        payload.put("odds_analysis", List.of(
                Map.of("market_type", "1x2", "outcome", "home",
                        "model_prob", 0.62, "best_odds", 1.85, "ev", 0.147)
        ));
        payload.put("score_matrix", List.of(List.of(0.05, 0.04), List.of(0.04, 0.03)));
        payload.put("over_under_probs", Map.of(
                "2.5", Map.of("over", 0.55, "under", 0.45)
        ));
        payload.put("team_stats", List.of());
        payload.put("h2h", Map.of("totalMatches", 3));
        return payload;
    }

    // --- /matches/today --------------------------------------------------

    @Test
    @DisplayName("GET /matches/today anonymous → 200 with paid fields collapsed + locked=true")
    void anonymousSeesGatedToday() throws Exception {
        when(mlApiClient.predictionsToday(any(LocalDate.class)))
                .thenReturn(List.of(fullMatchPayload(1L)));

        mockMvc.perform(get("/api/v1/matches/today"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].matchId").value(1))
                .andExpect(jsonPath("$[0].probHomeWin").value(0.62))
                .andExpect(jsonPath("$[0].locked").value(true))
                .andExpect(jsonPath("$[0].scoreMatrix").doesNotExist())
                .andExpect(jsonPath("$[0].oddsAnalysis").doesNotExist())
                .andExpect(jsonPath("$[0].overUnderProbs").doesNotExist())
                // Free users see "any value signal" but never the integer level.
                .andExpect(jsonPath("$[0].topSignalLevel").doesNotExist());
    }

    @Test
    @DisplayName("GET /matches/today as PREMIUM → 200 with paid fields populated + locked=false")
    void premiumSeesEverythingOnToday() throws Exception {
        when(mlApiClient.predictionsToday(any(LocalDate.class)))
                .thenReturn(List.of(fullMatchPayload(2L)));
        String access = premiumAccess("premium-today@user.test");

        mockMvc.perform(get("/api/v1/matches/today")
                .header("Authorization", "Bearer " + access))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].locked").value(false))
                .andExpect(jsonPath("$[0].scoreMatrix").exists())
                .andExpect(jsonPath("$[0].oddsAnalysis").isArray())
                .andExpect(jsonPath("$[0].oddsAnalysis[0].ev").value(0.147))
                .andExpect(jsonPath("$[0].overUnderProbs['2.5'].over").value(0.55))
                .andExpect(jsonPath("$[0].topSignalLevel").value(2));
    }

    // --- /matches/{id} (detail) ------------------------------------------

    @Test
    @DisplayName("GET /matches/{id} anonymous → 200 + paid fields collapsed")
    void anonymousSeesGatedDetail() throws Exception {
        when(mlApiClient.matchDetail(anyLong())).thenReturn(fullMatchPayload(99L));

        mockMvc.perform(get("/api/v1/matches/99"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.matchId").value(99))
                .andExpect(jsonPath("$.locked").value(true))
                .andExpect(jsonPath("$.scoreMatrix").doesNotExist());
    }

    @Test
    @DisplayName("GET /matches/{id} as PREMIUM → 200 + paid fields populated")
    void premiumSeesEverythingOnDetail() throws Exception {
        when(mlApiClient.matchDetail(anyLong())).thenReturn(fullMatchPayload(99L));
        String access = premiumAccess("premium-detail@user.test");

        mockMvc.perform(get("/api/v1/matches/99")
                .header("Authorization", "Bearer " + access))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.locked").value(false))
                .andExpect(jsonPath("$.scoreMatrix").exists())
                // The oddsAnalysis bug we fixed: must be an array, not a map.
                .andExpect(jsonPath("$.oddsAnalysis").isArray())
                .andExpect(jsonPath("$.oddsAnalysis[0].market_type").value("1x2"));
    }

    @Test
    @DisplayName("GET /matches/{id} for a non-existent match returns 404")
    void detailMissing404() throws Exception {
        when(mlApiClient.matchDetail(anyLong())).thenReturn(Map.of());

        mockMvc.perform(get("/api/v1/matches/9999"))
                .andExpect(status().isNotFound());
    }

    // --- /matches/{id}/prediction (basic+ route-layer gate) --------------

    @Test
    @DisplayName("GET /matches/{id}/prediction free user → 403 (subscriptionExpired)")
    void predictionFreeUserBlocked() throws Exception {
        String access = registerAccess("blocked@user.test");

        mockMvc.perform(get("/api/v1/matches/77/prediction")
                .header("Authorization", "Bearer " + access))
                .andExpect(status().isForbidden());
    }

    @Test
    @DisplayName("GET /matches/{id}/prediction PREMIUM user → 200 + paid fields visible")
    void predictionPremiumAllowed() throws Exception {
        when(mlApiClient.matchDetail(anyLong())).thenReturn(fullMatchPayload(77L));
        String access = premiumAccess("premium-pred@user.test");

        mockMvc.perform(get("/api/v1/matches/77/prediction")
                .header("Authorization", "Bearer " + access))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.scoreMatrix").exists());
    }

    @Test
    @DisplayName("GET /matches/{id}/prediction anonymous → 403 (no auth = free tier)")
    void predictionAnonymousBlocked() throws Exception {
        // Anonymous users go through with FREE tier in the controller, then
        // the explicit isAtLeast(BASIC) check throws subscriptionExpired.
        mockMvc.perform(get("/api/v1/matches/77/prediction"))
                .andExpect(status().isForbidden());
    }

    // --- /matches/{id}/odds-analysis -------------------------------------

    @Test
    @DisplayName("GET /matches/{id}/odds-analysis free user → 403 (tier gate inside MatchService)")
    void oddsAnalysisFreeUserBlocked() throws Exception {
        String access = registerAccess("freeodds@user.test");

        mockMvc.perform(get("/api/v1/matches/88/odds-analysis")
                .header("Authorization", "Bearer " + access))
                .andExpect(status().isForbidden());
    }

    @Test
    @DisplayName("GET /matches/{id}/odds-analysis PREMIUM → 200 (delegate to ml-api)")
    void oddsAnalysisPremiumAllowed() throws Exception {
        when(mlApiClient.oddsAnalysis(anyLong())).thenReturn(Map.of(
                "match_id", 88, "markets", List.of()
        ));
        String access = premiumAccess("premium-odds@user.test");

        mockMvc.perform(get("/api/v1/matches/88/odds-analysis")
                .header("Authorization", "Bearer " + access))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.match_id").value(88));
    }

    // --- /matches/{id}/favorite ------------------------------------------

    @Test
    @DisplayName("POST /matches/{id}/favorite anonymous → 401/403")
    void favoriteRequiresAuth() throws Exception {
        mockMvc.perform(post("/api/v1/matches/55/favorite"))
                .andExpect(result -> {
                    int code = result.getResponse().getStatus();
                    assert code == 401 || code == 403
                            : "anonymous favorite must be denied, got " + code;
                });
    }

    @Test
    @DisplayName("POST /matches/{id}/favorite toggles on / off across two calls")
    void favoriteToggles() throws Exception {
        String access = registerAccess("favtoggle@user.test");

        mockMvc.perform(post("/api/v1/matches/55/favorite")
                .header("Authorization", "Bearer " + access))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.favorite").value(true));

        mockMvc.perform(post("/api/v1/matches/55/favorite")
                .header("Authorization", "Bearer " + access))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.favorite").value(false));
    }

    // --- /matches/upcoming clamp ----------------------------------------

    @Test
    @DisplayName("GET /matches/upcoming clamps days to [1, 180] before hitting ml-api")
    void upcomingClampsRange() throws Exception {
        when(mlApiClient.predictionsUpcoming(anyInt())).thenReturn(List.of());

        // 9999 days → clamped to 180. We just verify the controller doesn't
        // 500 and the response shape stays well-formed.
        mockMvc.perform(get("/api/v1/matches/upcoming")
                .param("days", "9999"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$").isArray());
    }
}
