package com.wcp.hedge;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.node.ObjectNode;
import com.wcp.integration.IntegrationTestBase;
import java.util.Map;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;

/**
 * Auth + tier-gating boundary tests for the M9 hedge controller.
 *
 * <p>Business-logic depth is covered by {@link HedgeServiceTest} with
 * mocked deps; this file just verifies the HTTP edges that Spring
 * Security + Spring MVC own.
 */
class HedgeControllerIntegrationTest extends IntegrationTestBase {

    private static final String SCENARIOS_PATH = "/api/v1/hedge/scenarios";
    private static final String STATS_PATH = "/api/v1/hedge/stats";

    // --- /scenarios (premium-gated) ----------------------------------------

    @Test
    @DisplayName("POST /scenarios anonymous → 403")
    void createScenarioRequiresAuth() throws Exception {
        ObjectNode body = singleScenarioBody();
        mockMvc.perform(post(SCENARIOS_PATH)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body.toString()))
                .andExpect(status().isForbidden());
    }

    @Test
    @DisplayName("GET /scenarios anonymous → 403")
    void listScenariosRequiresAuth() throws Exception {
        mockMvc.perform(get(SCENARIOS_PATH)).andExpect(status().isForbidden());
    }

    @Test
    @DisplayName("POST /scenarios with FREE-tier user → 403 (premium required)")
    void createScenarioFreeUserForbidden() throws Exception {
        // Fresh registration defaults to "free" — never paid, so this exercises
        // the premium gate as long as the request is otherwise well-formed.
        String access = registerAccess("hedge-free@user.test");
        ObjectNode body = singleScenarioBody();
        mockMvc.perform(post(SCENARIOS_PATH)
                        .header("Authorization", "Bearer " + access)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(body.toString()))
                .andExpect(status().isForbidden())
                .andExpect(jsonPath("$.error").value("FORBIDDEN"));
    }

    @Test
    @DisplayName("GET /scenarios with FREE-tier user → 403")
    void listScenariosFreeUserForbidden() throws Exception {
        String access = registerAccess("hedge-free-list@user.test");
        mockMvc.perform(get(SCENARIOS_PATH).header("Authorization", "Bearer " + access))
                .andExpect(status().isForbidden());
    }

    // --- /stats (basic+) ----------------------------------------------------

    @Test
    @DisplayName("GET /stats anonymous → 403")
    void statsRequiresAuth() throws Exception {
        mockMvc.perform(get(STATS_PATH)).andExpect(status().isForbidden());
    }

    @Test
    @DisplayName("GET /stats free-tier → 403 (basic+ required)")
    void statsFreeUserForbidden() throws Exception {
        String access = registerAccess("hedge-stats-free@user.test");
        mockMvc.perform(get(STATS_PATH).header("Authorization", "Bearer " + access))
                .andExpect(status().isForbidden());
    }

    // --- /scenarios/{id} & {id}/recalc & /results --------------------------

    @Test
    @DisplayName("GET /scenarios/{id} anonymous → 403")
    void getScenarioRequiresAuth() throws Exception {
        mockMvc.perform(get(SCENARIOS_PATH + "/1")).andExpect(status().isForbidden());
    }

    @Test
    @DisplayName("POST /scenarios/{id}/recalc anonymous → 403")
    void recalcRequiresAuth() throws Exception {
        mockMvc.perform(post(SCENARIOS_PATH + "/1/recalc")).andExpect(status().isForbidden());
    }

    @Test
    @DisplayName("GET /results anonymous → 403")
    void resultsRequiresAuth() throws Exception {
        mockMvc.perform(get("/api/v1/hedge/results")).andExpect(status().isForbidden());
    }

    // -----------------------------------------------------------------------
    // helpers
    // -----------------------------------------------------------------------

    /** Register a new user and return their JWT access token. */
    private String registerAccess(String email) throws Exception {
        ObjectNode body = objectMapper.createObjectNode()
                .put("email", email)
                .put("password", "Password123");
        return objectMapper.readTree(
                        mockMvc.perform(post("/api/v1/auth/register")
                                        .contentType(MediaType.APPLICATION_JSON)
                                        .content(body.toString()))
                                .andExpect(status().isCreated())
                                .andReturn()
                                .getResponse()
                                .getContentAsString())
                .get("accessToken")
                .asText();
    }

    private ObjectNode singleScenarioBody() {
        return objectMapper.createObjectNode()
                .put("scenarioType", "single")
                .put("matchId", 123L)
                .put("originalStake", "100")
                .put("originalOdds", "2.10")
                .put("originalOutcome", "home")
                .put("originalMarket", "1x2")
                .put("hedgeMode", "full");
    }
}
