package com.wcp.service;

import com.wcp.client.MlApiClient;
import com.wcp.dto.response.MatchSummaryResponse;
import com.wcp.exception.ApiException;
import com.wcp.model.UserFavorite;
import com.wcp.model.enums.SubscriptionTier;
import com.wcp.repository.UserFavoriteRepository;
import com.wcp.security.UserPrincipal;
import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Match-data dispatcher.
 *
 * <p>Pulls today's predictions / per-match detail from the Python ML API,
 * then runs everything through {@link ContentTierService} before handing it
 * to the controllers. Also owns the user's favorites toggle since it sits
 * naturally next to the match read path.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class MatchService {

    private final MlApiClient mlApiClient;
    private final ContentTierService contentTierService;
    private final UserFavoriteRepository favoriteRepository;

    public List<MatchSummaryResponse> getTodayMatches(LocalDate date, SubscriptionTier tier) {
        List<Map<String, Object>> raw = mlApiClient.predictionsToday(date);
        return raw.stream()
                .map(MatchService::toMatchSummary)
                .map(s -> contentTierService.applyTier(s, tier))
                .toList();
    }

    public MatchSummaryResponse getMatchDetail(long matchId, SubscriptionTier tier) {
        Map<String, Object> body = mlApiClient.predict(matchId, true);
        if (body.isEmpty()) {
            throw ApiException.notFound("match prediction");
        }
        return contentTierService.applyTier(toMatchSummary(body), tier);
    }

    public Map<String, Object> getOddsAnalysis(long matchId, SubscriptionTier tier) {
        if (!tier.isAtLeast(SubscriptionTier.BASIC)) {
            throw ApiException.subscriptionExpired();
        }
        return mlApiClient.oddsAnalysis(matchId);
    }

    @Transactional
    public boolean toggleFavorite(UserPrincipal principal, long matchId) {
        if (principal == null || principal.id() == null) {
            throw ApiException.unauthorized("login required");
        }
        Optional<UserFavorite> existing = favoriteRepository.findByUserIdAndMatchId(
                principal.id(), matchId);
        if (existing.isPresent()) {
            favoriteRepository.delete(existing.get());
            return false;
        }
        favoriteRepository.save(UserFavorite.builder()
                .userId(principal.id())
                .matchId(matchId)
                .createdAt(Instant.now())
                .build());
        return true;
    }

    // --- Mappers ---

    @SuppressWarnings("unchecked")
    private static MatchSummaryResponse toMatchSummary(Map<String, Object> raw) {
        return new MatchSummaryResponse(
                asLong(raw.get("match_id")),
                asInstant(raw.get("match_date")),
                (String) raw.getOrDefault("home_team", "?"),
                (String) raw.getOrDefault("away_team", "?"),
                (String) raw.get("competition"),
                (String) raw.getOrDefault("status", "scheduled"),
                asDouble(raw.get("prob_home_win")),
                asDouble(raw.get("prob_draw")),
                asDouble(raw.get("prob_away_win")),
                asInteger(raw.get("confidence_score")),
                (String) raw.get("confidence_level"),
                raw.containsKey("top_signal_level")
                        ? asInteger(raw.get("top_signal_level")) != null
                                && (Integer) raw.get("top_signal_level") > 0
                        : null,
                asInteger(raw.get("top_signal_level")),
                (Map<String, Object>) raw.get("odds_analysis"),
                (Map<String, Object>) raw.get("score_matrix"),
                (Map<String, Object>) raw.get("over_under_probs"),
                false
        );
    }

    private static Long asLong(Object value) {
        return value instanceof Number n ? n.longValue() : null;
    }

    private static Double asDouble(Object value) {
        return value instanceof Number n ? n.doubleValue() : null;
    }

    private static Integer asInteger(Object value) {
        return value instanceof Number n ? n.intValue() : null;
    }

    private static Instant asInstant(Object value) {
        if (value instanceof String s && !s.isBlank()) {
            try {
                return Instant.parse(s.endsWith("Z") ? s : s + "Z");
            } catch (Exception ignored) {
                return null;
            }
        }
        return null;
    }
}
