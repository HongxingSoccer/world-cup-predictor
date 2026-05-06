package com.wcp.client;

import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.UriComponentsBuilder;

/**
 * HTTP client for the Python ML FastAPI service.
 *
 * <p>All calls degrade gracefully — a transport failure / 5xx response
 * returns an empty payload + a logged warning rather than propagating.
 * The web tier renders the public match-list with no predictions in that
 * case so the front-end never breaks because ML is down.
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class MlApiClient {

    private final @Qualifier("mlApiRestTemplate") RestTemplate restTemplate;

    @SuppressWarnings("unchecked")
    public List<Map<String, Object>> predictionsUpcoming(int days) {
        String url = UriComponentsBuilder.fromPath("/api/v1/predictions/upcoming")
                .queryParam("days", days)
                .toUriString();
        try {
            Map<String, Object> body = restTemplate.getForObject(url, Map.class);
            if (body == null) {
                return List.of();
            }
            Object items = body.get("items");
            if (items instanceof List<?> list) {
                return list.stream()
                        .filter(Map.class::isInstance)
                        .map(o -> (Map<String, Object>) o)
                        .toList();
            }
            return List.of();
        } catch (HttpClientErrorException ex) {
            log.warn("ml_api_predictions_upcoming_4xx status={} body={}", ex.getStatusCode(), ex.getResponseBodyAsString());
            return List.of();
        } catch (RestClientException ex) {
            log.warn("ml_api_predictions_upcoming_failed error={}", ex.getMessage());
            return List.of();
        }
    }

    @SuppressWarnings("unchecked")
    public List<Map<String, Object>> predictionsToday(LocalDate date) {
        String url = UriComponentsBuilder.fromPath("/api/v1/predictions/today")
                .queryParam("date", date.toString())
                .toUriString();
        try {
            Map<String, Object> body = restTemplate.getForObject(url, Map.class);
            if (body == null) {
                return List.of();
            }
            Object items = body.get("items");
            if (items instanceof List<?> list) {
                return list.stream()
                        .filter(Map.class::isInstance)
                        .map(o -> (Map<String, Object>) o)
                        .toList();
            }
            return List.of();
        } catch (HttpClientErrorException ex) {
            log.warn("ml_api_predictions_today_4xx status={} body={}", ex.getStatusCode(), ex.getResponseBodyAsString());
            return List.of();
        } catch (RestClientException ex) {
            log.warn("ml_api_predictions_today_failed error={}", ex.getMessage());
            return List.of();
        }
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> predict(long matchId, boolean includeScoreMatrix) {
        Map<String, Object> request = Map.of(
                "match_id", matchId,
                "include_score_matrix", includeScoreMatrix,
                "publish", false
        );
        try {
            Map<String, Object> body = restTemplate.postForObject("/api/v1/predict", request, Map.class);
            return body == null ? Map.of() : body;
        } catch (HttpClientErrorException ex) {
            log.warn("ml_api_predict_4xx match={} status={}", matchId, ex.getStatusCode());
            return Map.of();
        } catch (RestClientException ex) {
            log.warn("ml_api_predict_failed match={} error={}", matchId, ex.getMessage());
            return Map.of();
        }
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> oddsAnalysis(long matchId) {
        Map<String, Object> request = Map.of("match_id", matchId);
        try {
            Map<String, Object> body = restTemplate.postForObject("/api/v1/odds-analysis", request, Map.class);
            return body == null ? Map.of() : body;
        } catch (RestClientException ex) {
            log.warn("ml_api_odds_failed match={} error={}", matchId, ex.getMessage());
            return Map.of();
        }
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> worldcupStandings() {
        try {
            Map<String, Object> body = restTemplate.getForObject(
                    "/api/v1/competitions/worldcup/standings", Map.class);
            return body == null ? Map.of("groups", List.of()) : body;
        } catch (RestClientException ex) {
            log.warn("ml_api_worldcup_standings_failed error={}", ex.getMessage());
            return Map.of("groups", List.of());
        }
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> worldcupBracket() {
        try {
            Map<String, Object> body = restTemplate.getForObject(
                    "/api/v1/competitions/worldcup/bracket", Map.class);
            return body == null ? Map.of("rounds", List.of()) : body;
        } catch (RestClientException ex) {
            log.warn("ml_api_worldcup_bracket_failed error={}", ex.getMessage());
            return Map.of("rounds", List.of());
        }
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> worldcupTeamPath(long teamId) {
        try {
            Map<String, Object> body = restTemplate.getForObject(
                    "/api/v1/worldcup/team/" + teamId + "/path", Map.class);
            return body == null ? Map.of() : body;
        } catch (RestClientException ex) {
            // 404 either means no simulation exists yet OR the team isn't in
            // the most recent simulation. Either way the caller renders an
            // empty state, so swallow + log.
            log.info("ml_api_worldcup_team_path_unavailable team={} error={}", teamId, ex.getMessage());
            return Map.of();
        }
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> worldcupSimulation() {
        try {
            Map<String, Object> body = restTemplate.getForObject(
                    "/api/v1/worldcup/simulation", Map.class);
            return body == null ? Map.of("results", Map.of("leaderboard", List.of())) : body;
        } catch (RestClientException ex) {
            // Includes 404 SIMULATION_NOT_FOUND when no Monte Carlo run has been
            // persisted yet — return an empty payload so the frontend can render
            // a "no simulation yet" state instead of failing.
            log.info("ml_api_worldcup_simulation_unavailable error={}", ex.getMessage());
            return Map.of("results", Map.of("leaderboard", List.of()));
        }
    }
}
