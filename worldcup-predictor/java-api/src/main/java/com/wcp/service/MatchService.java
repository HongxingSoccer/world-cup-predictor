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

    public List<MatchSummaryResponse> getUpcomingMatches(int days, SubscriptionTier tier) {
        List<Map<String, Object>> raw = mlApiClient.predictionsUpcoming(days);
        return raw.stream()
                .map(MatchService::toMatchSummary)
                .map(s -> contentTierService.applyTier(s, tier))
                .toList();
    }

    public MatchSummaryResponse getMatchDetail(long matchId, SubscriptionTier tier) {
        // Read endpoint never invokes the model — returns metadata + the
        // latest persisted prediction (if any) + form / H2H. Empty payload
        // means the match row itself is missing → propagate 404.
        Map<String, Object> body = mlApiClient.matchDetail(matchId);
        if (body.isEmpty()) {
            throw ApiException.notFound("match");
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

    /**
     * Flattens the three shapes the Python ML API returns for a match prediction:
     *
     * <ul>
     *   <li>{@code GET /predictions/today} items — flat keys, {@code home_team}
     *       is a String, probabilities live at the top level.</li>
     *   <li>{@code POST /predict} body — {@code home_team} is a
     *       {@code {id,name,name_zh}} object, probs and {@code over_under_probs}
     *       are nested under a {@code predictions} sub-object, and there is no
     *       top-level {@code status}.</li>
     *   <li>{@code GET /matches/{id}} body — flat keys including {@code team_stats},
     *       {@code h2h}, {@code odds_analysis}, {@code score_matrix}.</li>
     * </ul>
     */
    @SuppressWarnings("unchecked")
    private static MatchSummaryResponse toMatchSummary(Map<String, Object> raw) {
        Map<String, Object> probs = raw.get("predictions") instanceof Map<?, ?> p
                ? (Map<String, Object>) p
                : raw;
        Integer topSignalLevel = asInteger(raw.get("top_signal_level"));
        Boolean hasValueSignal = raw.get("has_value_signal") instanceof Boolean b
                ? b
                : (topSignalLevel != null ? topSignalLevel > 0 : null);
        Object oddsAnalysis = raw.get("odds_analysis");
        return new MatchSummaryResponse(
                asLong(raw.get("match_id")),
                asInstant(raw.get("match_date")),
                asTeamName(raw.get("home_team")),
                asTeamName(raw.get("away_team")),
                (String) raw.get("competition"),
                (String) raw.getOrDefault("status", "scheduled"),
                asDouble(probs.get("prob_home_win")),
                asDouble(probs.get("prob_draw")),
                asDouble(probs.get("prob_away_win")),
                asInteger(raw.get("confidence_score")),
                (String) raw.get("confidence_level"),
                hasValueSignal,
                topSignalLevel,
                oddsAnalysis instanceof Map<?, ?> m ? (Map<String, Object>) m : null,
                probs.get("score_matrix"),
                asMap(probs.get("over_under_probs")),
                false,
                asListOfMaps(raw.get("team_stats")),
                asMap(raw.get("h2h")),
                (String) raw.get("venue"),
                (String) raw.get("round"),
                asInteger(raw.get("home_score")),
                asInteger(raw.get("away_score"))
        );
    }

    @SuppressWarnings("unchecked")
    private static java.util.List<Map<String, Object>> asListOfMaps(Object value) {
        if (!(value instanceof java.util.List<?> list)) {
            return null;
        }
        return list.stream()
                .filter(Map.class::isInstance)
                .map(o -> (Map<String, Object>) o)
                .toList();
    }

    @SuppressWarnings("unchecked")
    private static Map<String, Object> asMap(Object value) {
        return value instanceof Map<?, ?> m ? (Map<String, Object>) m : null;
    }

    private static String asTeamName(Object value) {
        if (value instanceof String s) {
            return s;
        }
        if (value instanceof Map<?, ?> m) {
            Object name = m.get("name");
            if (name instanceof String s) {
                return s;
            }
        }
        return "?";
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
