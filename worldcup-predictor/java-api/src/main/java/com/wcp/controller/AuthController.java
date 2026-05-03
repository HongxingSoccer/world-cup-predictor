package com.wcp.controller;

import com.wcp.dto.request.LoginRequest;
import com.wcp.dto.request.RefreshTokenRequest;
import com.wcp.dto.request.RegisterRequest;
import com.wcp.dto.response.AuthResponse;
import com.wcp.exception.ApiException;
import com.wcp.service.AuthService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/auth")
@RequiredArgsConstructor
@Tag(name = "auth", description = "Registration, login, OAuth, token-refresh, logout.")
public class AuthController {

    private final AuthService authService;

    @PostMapping("/register")
    @Operation(summary = "Register with phone OR email + password.")
    public ResponseEntity<AuthResponse> register(@Valid @RequestBody RegisterRequest req) {
        return ResponseEntity.status(HttpStatus.CREATED).body(authService.register(req));
    }

    @PostMapping("/login")
    @Operation(summary = "Password-based login.")
    public ResponseEntity<AuthResponse> login(@Valid @RequestBody LoginRequest req) {
        return ResponseEntity.ok(authService.login(req));
    }

    @PostMapping("/refresh")
    @Operation(summary = "Exchange a refresh token for a fresh access token.")
    public ResponseEntity<AuthResponse> refresh(@Valid @RequestBody RefreshTokenRequest req) {
        return ResponseEntity.ok(authService.refresh(req.refreshToken()));
    }

    @PostMapping("/logout")
    @Operation(summary = "Revoke the bearer access token via Redis blacklist.")
    public ResponseEntity<Void> logout(HttpServletRequest request) {
        String header = request.getHeader("Authorization");
        if (header == null || !header.startsWith("Bearer ")) {
            throw ApiException.badRequest("missing bearer token");
        }
        authService.logout(header.substring("Bearer ".length()).trim());
        return ResponseEntity.noContent().build();
    }

    @PostMapping("/oauth/{provider}")
    @Operation(summary = "OAuth callback (Phase 3 stub).")
    public ResponseEntity<AuthResponse> oauth(
            @PathVariable String provider,
            @RequestBody java.util.Map<String, Object> body
    ) {
        // TODO(Phase 3.5): wire WeChat / Google / Apple flows. Spec calls for
        // a strategy interface keyed on `provider`; the AuthService hook will
        // mirror `register()` once implemented.
        throw ApiException.badRequest("OAuth provider " + provider + " not yet wired");
    }
}
