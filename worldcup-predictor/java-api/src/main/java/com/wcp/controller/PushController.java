package com.wcp.controller;

import com.wcp.client.MlApiClient;
import com.wcp.exception.ApiException;
import com.wcp.security.UserPrincipal;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import java.util.HashMap;
import java.util.Map;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Authenticated push-preferences proxy.
 *
 * <p>The ml-api endpoint takes a user_id query param and is internal — Java
 * is the auth boundary. We extract the principal id, forward to ml-api, and
 * never let the client choose whose settings to read or write.
 */
@RestController
@RequestMapping("/api/v1/push/settings")
@RequiredArgsConstructor
@Tag(name = "push", description = "Push notification preferences (per user).")
public class PushController {

    private final MlApiClient mlApiClient;

    @GetMapping
    @Operation(summary = "Read the current user's push preferences.")
    public ResponseEntity<Map<String, Object>> read(
            @AuthenticationPrincipal UserPrincipal principal
    ) {
        if (principal == null || principal.id() == null) {
            throw ApiException.unauthorized("login required");
        }
        return ResponseEntity.ok(mlApiClient.getPushSettings(principal.id()));
    }

    @PutMapping
    @Operation(summary = "Update the current user's push preferences.")
    public ResponseEntity<Map<String, Object>> update(
            @AuthenticationPrincipal UserPrincipal principal,
            @RequestBody Map<String, Object> body
    ) {
        if (principal == null || principal.id() == null) {
            throw ApiException.unauthorized("login required");
        }
        // Force user_id from the principal — never trust a client-supplied
        // id, even via the body. The client form omits this field.
        Map<String, Object> payload = new HashMap<>(body == null ? Map.of() : body);
        payload.put("user_id", principal.id());
        return ResponseEntity.ok(mlApiClient.putPushSettings(payload));
    }
}
