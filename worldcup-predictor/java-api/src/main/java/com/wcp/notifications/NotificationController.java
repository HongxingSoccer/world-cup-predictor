package com.wcp.notifications;

import com.wcp.exception.ApiException;
import com.wcp.notifications.dto.NotificationResponse;
import com.wcp.security.UserPrincipal;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import java.util.Map;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/notifications")
@RequiredArgsConstructor
@Tag(name = "notifications", description = "M9.5 notification centre.")
public class NotificationController {

    private final NotificationService service;

    @GetMapping
    @Operation(summary = "List the caller's notifications + unread-count.")
    public ResponseEntity<Map<String, Object>> list(
            @AuthenticationPrincipal UserPrincipal principal,
            @RequestParam(defaultValue = "50") int limit) {
        requireBasic(principal);
        return ResponseEntity.ok(service.list(principal, limit));
    }

    @GetMapping("/unread-count")
    @Operation(summary = "Just the unread count — cheap, suitable for 30s polling.")
    public ResponseEntity<Map<String, Object>> unreadCount(
            @AuthenticationPrincipal UserPrincipal principal) {
        requireBasic(principal);
        return ResponseEntity.ok(Map.of("unreadCount", service.unreadCount(principal)));
    }

    @PatchMapping("/{id}/read")
    @Operation(summary = "Mark a single notification read.")
    public ResponseEntity<NotificationResponse> markRead(
            @AuthenticationPrincipal UserPrincipal principal,
            @PathVariable Long id) {
        requireBasic(principal);
        return ResponseEntity.ok(service.markRead(principal, id));
    }

    @PostMapping("/read-all")
    @Operation(summary = "Mark every unread notification read.")
    public ResponseEntity<Map<String, Object>> markAllRead(
            @AuthenticationPrincipal UserPrincipal principal) {
        requireBasic(principal);
        return ResponseEntity.ok(Map.of("updated", service.markAllRead(principal)));
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
