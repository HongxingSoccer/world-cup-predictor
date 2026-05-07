package com.wcp.controller;

import com.wcp.dto.response.MatchSummaryResponse;
import com.wcp.exception.ApiException;
import com.wcp.model.enums.SubscriptionTier;
import com.wcp.security.UserPrincipal;
import com.wcp.service.MatchService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Map;
import lombok.RequiredArgsConstructor;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@Tag(name = "matches", description = "Public match list + tier-aware predictions + favorites.")
public class MatchController {

    private final MatchService matchService;

    @GetMapping("/api/v1/matches/today")
    @Operation(summary = "Today's matches with tier-aware prediction summary.")
    public ResponseEntity<List<MatchSummaryResponse>> today(
            @RequestParam(required = false)
            @DateTimeFormat(iso = DateTimeFormat.ISO.DATE) LocalDate date,
            @AuthenticationPrincipal UserPrincipal principal
    ) {
        LocalDate target = (date != null) ? date : LocalDate.now(ZoneOffset.UTC);
        SubscriptionTier tier = (principal != null) ? principal.subscriptionTier() : SubscriptionTier.FREE;
        return ResponseEntity.ok(matchService.getTodayMatches(target, tier));
    }

    @GetMapping("/api/v1/matches/upcoming")
    @Operation(summary = "Predictions for matches kicking off in the next N days.")
    public ResponseEntity<List<MatchSummaryResponse>> upcoming(
            @RequestParam(defaultValue = "60") int days,
            @AuthenticationPrincipal UserPrincipal principal
    ) {
        // Clamp the window so a malicious caller can't trigger a multi-year scan.
        int clamped = Math.max(1, Math.min(days, 180));
        SubscriptionTier tier = (principal != null) ? principal.subscriptionTier() : SubscriptionTier.FREE;
        return ResponseEntity.ok(matchService.getUpcomingMatches(clamped, tier));
    }

    @GetMapping("/api/v1/matches/{id}")
    @Operation(summary = "Match detail with tier-aware prediction body.")
    public ResponseEntity<MatchSummaryResponse> detail(
            @PathVariable long id,
            @AuthenticationPrincipal UserPrincipal principal
    ) {
        return ResponseEntity.ok(matchService.getMatchDetail(id, principal));
    }

    @GetMapping("/api/v1/matches/{id}/prediction")
    @Operation(summary = "Same as /matches/{id} but rejected at the route layer for free users.")
    public ResponseEntity<MatchSummaryResponse> prediction(
            @PathVariable long id,
            @AuthenticationPrincipal UserPrincipal principal
    ) {
        SubscriptionTier tier = (principal != null) ? principal.subscriptionTier() : SubscriptionTier.FREE;
        if (!tier.isAtLeast(SubscriptionTier.BASIC)) {
            throw ApiException.subscriptionExpired();
        }
        return ResponseEntity.ok(matchService.getMatchDetail(id, principal));
    }

    @GetMapping("/api/v1/matches/{id}/odds-analysis")
    @Operation(summary = "Per-match odds analysis (basic+).")
    public ResponseEntity<Map<String, Object>> oddsAnalysis(
            @PathVariable long id,
            @AuthenticationPrincipal UserPrincipal principal
    ) {
        SubscriptionTier tier = (principal != null) ? principal.subscriptionTier() : SubscriptionTier.FREE;
        return ResponseEntity.ok(matchService.getOddsAnalysis(id, tier));
    }

    @PostMapping("/api/v1/matches/{id}/favorite")
    @Operation(summary = "Toggle the current user's favorite for the given match.")
    public ResponseEntity<Map<String, Object>> toggleFavorite(
            @PathVariable long id,
            @AuthenticationPrincipal UserPrincipal principal
    ) {
        boolean nowFavorite = matchService.toggleFavorite(principal, id);
        return ResponseEntity.ok(Map.of("matchId", id, "favorite", nowFavorite));
    }

    @GetMapping("/api/v1/matches/{id}/related")
    @Operation(summary = "Sibling matches in the same season / round.")
    public ResponseEntity<List<Map<String, Object>>> related(
            @PathVariable long id,
            @RequestParam(defaultValue = "6") int limit
    ) {
        int clamped = Math.max(1, Math.min(limit, 20));
        return ResponseEntity.ok(matchService.getRelatedMatches(id, clamped));
    }

    @GetMapping("/api/v1/users/me/favorites")
    @Operation(summary = "Authenticated caller's favourite matches with summary metadata.")
    public ResponseEntity<List<Map<String, Object>>> myFavorites(
            @AuthenticationPrincipal UserPrincipal principal
    ) {
        if (principal == null || principal.id() == null) {
            throw ApiException.unauthorized("login required");
        }
        return ResponseEntity.ok(matchService.getFavoritesForUser(principal));
    }
}
