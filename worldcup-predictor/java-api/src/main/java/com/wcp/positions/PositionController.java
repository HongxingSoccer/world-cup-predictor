package com.wcp.positions;

import com.wcp.exception.ApiException;
import com.wcp.positions.dto.CreatePositionRequest;
import com.wcp.positions.dto.PositionResponse;
import com.wcp.positions.dto.UpdateStatusRequest;
import com.wcp.security.UserPrincipal;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * M9.5 positions API on the business service.
 *
 * <p>Tier: basic+. Position tracking is a foundational feature, not a
 * premium one — the premium gates are on M9 hedging calculation + the
 * eventual push delivery, not on bookkeeping.
 */
@RestController
@RequestMapping("/api/v1/positions")
@RequiredArgsConstructor
@Tag(name = "positions", description = "User position tracker (M9.5).")
public class PositionController {

    private final PositionService service;

    @PostMapping
    @Operation(summary = "Create a new tracked position.")
    public ResponseEntity<PositionResponse> create(
            @AuthenticationPrincipal UserPrincipal principal,
            @Valid @RequestBody CreatePositionRequest req) {
        requireBasic(principal);
        return ResponseEntity.status(HttpStatus.CREATED).body(service.create(principal, req));
    }

    @GetMapping
    @Operation(summary = "List the caller's positions (optionally filtered by status).")
    public ResponseEntity<List<PositionResponse>> list(
            @AuthenticationPrincipal UserPrincipal principal,
            @RequestParam(required = false) String status) {
        requireBasic(principal);
        return ResponseEntity.ok(service.list(principal, status));
    }

    @GetMapping("/{id}")
    @Operation(summary = "Fetch a single position by id.")
    public ResponseEntity<PositionResponse> get(
            @AuthenticationPrincipal UserPrincipal principal,
            @PathVariable Long id) {
        requireBasic(principal);
        return ResponseEntity.ok(service.get(principal, id));
    }

    @PatchMapping("/{id}/status")
    @Operation(summary = "Change a position's status.")
    public ResponseEntity<PositionResponse> updateStatus(
            @AuthenticationPrincipal UserPrincipal principal,
            @PathVariable Long id,
            @Valid @RequestBody UpdateStatusRequest req) {
        requireBasic(principal);
        return ResponseEntity.ok(service.updateStatus(principal, id, req));
    }

    @DeleteMapping("/{id}")
    @Operation(summary = "Soft-delete (status → cancelled).")
    public ResponseEntity<PositionResponse> softDelete(
            @AuthenticationPrincipal UserPrincipal principal,
            @PathVariable Long id) {
        requireBasic(principal);
        return ResponseEntity.ok(service.softDelete(principal, id));
    }

    // ------------------------------------------------------------------
    // Tier gate
    // ------------------------------------------------------------------

    private static void requireBasic(UserPrincipal principal) {
        if (principal == null || principal.id() == null) {
            throw ApiException.unauthorized("login required");
        }
        // basic+ — anything except FREE
        if ("free".equalsIgnoreCase(principal.subscriptionTier().wireValue())) {
            throw ApiException.forbidden("basic subscription required");
        }
    }
}
