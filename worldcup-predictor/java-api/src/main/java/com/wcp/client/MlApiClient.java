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
}
