package com.wcp.hedge;

import com.wcp.exception.ApiException;
import com.wcp.hedge.dto.CreateScenarioRequest;
import com.wcp.hedge.dto.HedgeHistoryResponse;
import com.wcp.hedge.dto.HedgeStatsResponse;
import com.wcp.hedge.dto.RecalcResponse;
import com.wcp.hedge.dto.ScenarioResponse;
import com.wcp.model.enums.SubscriptionTier;
import com.wcp.security.UserPrincipal;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * M9 hedge advisory — business endpoints. Six routes per design §4.2.
 *
 * <p>Tier gating (design §6.4):
 *   - {@code POST/GET /scenarios*} and {@code /results} require <b>premium</b>
 *   - {@code /stats} is open to <b>basic+</b> (so non-premium users see
 *     aggregated platform value as a marketing surface)
 *   - All routes require an authenticated principal (JWT bearer).
 */
@RestController
@RequestMapping("/api/v1/hedge")
@RequiredArgsConstructor
@Tag(name = "hedge", description = "M9 hedging advisory — scenarios, recalc, history, stats.")
public class HedgeController {

    private final HedgeService hedgeService;

    // ------------------------------------------------------------------
    // POST /scenarios — create a hedge scenario
    // ------------------------------------------------------------------

    @PostMapping("/scenarios")
    @Operation(summary = "Create a hedge scenario (single or parlay).")
    public ResponseEntity<ScenarioResponse> createScenario(
            @AuthenticationPrincipal UserPrincipal principal,
            @Valid @RequestBody CreateScenarioRequest req) {
        requirePremium(principal);
        return ResponseEntity.ok(hedgeService.createScenario(principal, req));
    }

    // ------------------------------------------------------------------
    // GET /scenarios — paginated list of caller's scenarios
    // ------------------------------------------------------------------

    @GetMapping("/scenarios")
    @Operation(summary = "List the caller's hedge scenarios (newest first).")
    public ResponseEntity<Page<ScenarioResponse>> listScenarios(
            @AuthenticationPrincipal UserPrincipal principal,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        requirePremium(principal);
        Pageable pageable = PageRequest.of(Math.max(0, page), Math.min(100, Math.max(1, size)));
        return ResponseEntity.ok(hedgeService.listScenarios(principal, pageable));
    }

    // ------------------------------------------------------------------
    // GET /scenarios/{id} — detail
    // ------------------------------------------------------------------

    @GetMapping("/scenarios/{id}")
    @Operation(summary = "Fetch one of the caller's scenarios + its calculations.")
    public ResponseEntity<ScenarioResponse> getScenario(
            @AuthenticationPrincipal UserPrincipal principal,
            @PathVariable Long id) {
        requirePremium(principal);
        return ResponseEntity.ok(hedgeService.getScenario(principal, id));
    }

    // ------------------------------------------------------------------
    // POST /scenarios/{id}/recalc — re-run with current odds
    // ------------------------------------------------------------------

    @PostMapping("/scenarios/{id}/recalc")
    @Operation(summary = "Recompute hedge calculations using the latest live odds.")
    public ResponseEntity<RecalcResponse> recalculate(
            @AuthenticationPrincipal UserPrincipal principal,
            @PathVariable Long id) {
        requirePremium(principal);
        return ResponseEntity.ok(hedgeService.recalculate(principal, id));
    }

    // ------------------------------------------------------------------
    // GET /results — settled-scenario history
    // ------------------------------------------------------------------

    @GetMapping("/results")
    @Operation(summary = "Settlement history for the caller's hedge scenarios.")
    public ResponseEntity<HedgeHistoryResponse> results(
            @AuthenticationPrincipal UserPrincipal principal) {
        requirePremium(principal);
        return ResponseEntity.ok(hedgeService.listResults(principal));
    }

    // ------------------------------------------------------------------
    // GET /stats — aggregate ROI / win rate (basic tier OK)
    // ------------------------------------------------------------------

    @GetMapping("/stats")
    @Operation(summary = "Aggregate hedge stats — ROI, win rate, total P/L.")
    public ResponseEntity<HedgeStatsResponse> stats(
            @AuthenticationPrincipal UserPrincipal principal) {
        if (principal == null || principal.id() == null) {
            throw ApiException.unauthorized("login required");
        }
        if (!principal.subscriptionTier().isAtLeast(SubscriptionTier.BASIC)) {
            throw ApiException.forbidden("basic subscription required");
        }
        return ResponseEntity.ok(hedgeService.stats(principal));
    }

    // ------------------------------------------------------------------
    // Guards
    // ------------------------------------------------------------------

    private static void requirePremium(UserPrincipal principal) {
        if (principal == null || principal.id() == null) {
            throw ApiException.unauthorized("login required");
        }
        if (!principal.subscriptionTier().isAtLeast(SubscriptionTier.PREMIUM)) {
            throw ApiException.forbidden("premium subscription required");
        }
    }
}
