package com.wcp.arbitrage;

import com.wcp.arbitrage.dto.CreateWatchlistRequest;
import com.wcp.arbitrage.dto.WatchlistResponse;
import com.wcp.client.MlApiClient;
import com.wcp.exception.ApiException;
import com.wcp.security.UserPrincipal;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import java.math.BigDecimal;
import java.util.List;
import java.util.Map;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * M10 arbitrage API on the business service.
 *
 * <p>Opportunity reads proxy to ml-api (it owns the
 * {@code arb_opportunities} table and the scanner). Watchlist CRUD is
 * JPA-direct so we don't pay an extra round-trip for the per-user
 * filter management.
 *
 * <p>Tier: basic+ for the opportunity list (anti-leech); premium for
 * watchlist push delivery (premium-only push channel — basic gets the
 * in-app drawer instead).
 */
@RestController
@RequestMapping("/api/v1/arbitrage")
@RequiredArgsConstructor
@Tag(name = "arbitrage", description = "M10 cross-platform arbitrage scanner.")
public class ArbitrageController {

    private final MlApiClient mlApiClient;
    private final ArbWatchlistService watchlistService;

    @GetMapping("/opportunities")
    @Operation(summary = "List active arbitrage opportunities.")
    public ResponseEntity<List<Map<String, Object>>> listOpportunities(
            @AuthenticationPrincipal UserPrincipal principal,
            @RequestParam(required = false) String marketType,
            @RequestParam(required = false) BigDecimal minProfitMargin,
            @RequestParam(required = false, defaultValue = "50") int limit) {
        requireBasic(principal);
        return ResponseEntity.ok(
                mlApiClient.arbitrageOpportunities(marketType, minProfitMargin, limit));
    }

    @GetMapping("/opportunities/{id}")
    @Operation(summary = "Fetch a single arbitrage opportunity by id.")
    public ResponseEntity<Map<String, Object>> getOpportunity(
            @AuthenticationPrincipal UserPrincipal principal,
            @PathVariable Long id) {
        requireBasic(principal);
        return ResponseEntity.ok(mlApiClient.arbitrageOpportunity(id));
    }

    // ------------------------------------------------------------------
    // Watchlist
    // ------------------------------------------------------------------

    @GetMapping("/watchlist")
    @Operation(summary = "List the caller's watchlist rules.")
    public ResponseEntity<List<WatchlistResponse>> listWatchlist(
            @AuthenticationPrincipal UserPrincipal principal) {
        requireBasic(principal);
        return ResponseEntity.ok(watchlistService.list(principal));
    }

    @PostMapping("/watchlist")
    @Operation(summary = "Add a watchlist rule.")
    public ResponseEntity<WatchlistResponse> createWatchlist(
            @AuthenticationPrincipal UserPrincipal principal,
            @Valid @RequestBody CreateWatchlistRequest req) {
        requireBasic(principal);
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(watchlistService.create(principal, req));
    }

    @DeleteMapping("/watchlist/{id}")
    @Operation(summary = "Remove a watchlist rule.")
    public ResponseEntity<Void> deleteWatchlist(
            @AuthenticationPrincipal UserPrincipal principal,
            @PathVariable Long id) {
        requireBasic(principal);
        watchlistService.delete(principal, id);
        return ResponseEntity.noContent().build();
    }

    private static void requireBasic(UserPrincipal principal) {
        if (principal == null || principal.id() == null) {
            throw ApiException.unauthorized("login required");
        }
        if ("free".equalsIgnoreCase(principal.subscriptionTier().wireValue())) {
            throw ApiException.forbidden("basic subscription required");
        }
    }
}
