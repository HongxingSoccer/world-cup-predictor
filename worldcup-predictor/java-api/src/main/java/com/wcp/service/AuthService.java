package com.wcp.service;

import com.wcp.dto.request.LoginRequest;
import com.wcp.dto.request.RegisterRequest;
import com.wcp.dto.response.AuthResponse;
import com.wcp.dto.response.UserResponse;
import com.wcp.exception.ApiException;
import com.wcp.model.User;
import com.wcp.repository.UserRepository;
import com.wcp.security.JwtTokenProvider;
import com.wcp.security.UserPrincipal;
import io.jsonwebtoken.Claims;
import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Registration / login / token-refresh / logout. */
@Service
@RequiredArgsConstructor
@Slf4j
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenProvider tokenProvider;

    @Transactional
    public AuthResponse register(RegisterRequest req) {
        if ((req.phone() == null || req.phone().isBlank())
                && (req.email() == null || req.email().isBlank())) {
            throw ApiException.badRequest("either phone or email is required");
        }
        if (req.password() == null || req.password().isBlank()) {
            throw ApiException.badRequest("password is required");
        }
        if (req.phone() != null && userRepository.existsByPhone(req.phone())) {
            throw ApiException.conflict("phone already registered");
        }
        if (req.email() != null && userRepository.existsByEmail(req.email())) {
            throw ApiException.conflict("email already registered");
        }

        User user = User.builder()
                .uuid(UUID.randomUUID())
                .phone(req.phone())
                .email(req.email())
                .passwordHash(passwordEncoder.encode(req.password()))
                .nickname(req.nickname())
                .subscriptionTier("free")
                .locale("zh-CN")
                .timezone("Asia/Shanghai")
                .active(true)
                .role("user")
                .build();
        user = userRepository.save(user);
        log.info("user_registered uuid={}", user.getUuid());
        return issueAuthResponse(user);
    }

    @Transactional
    public AuthResponse login(LoginRequest req) {
        Optional<User> maybeUser = lookupForLogin(req);
        User user = maybeUser
                .filter(u -> u.getPasswordHash() != null
                        && passwordEncoder.matches(req.password(), u.getPasswordHash()))
                .orElseThrow(() -> ApiException.unauthorized("invalid credentials"));
        if (!user.isActive()) {
            throw ApiException.forbidden("account disabled");
        }
        user.recordLogin(Instant.now());
        return issueAuthResponse(user);
    }

    public AuthResponse refresh(String refreshToken) {
        Claims claims = tokenProvider.verify(refreshToken);
        if (!tokenProvider.isRefreshToken(claims)) {
            throw ApiException.unauthorized("not a refresh token");
        }
        UUID uuid;
        try {
            uuid = UUID.fromString(claims.getSubject());
        } catch (IllegalArgumentException ex) {
            throw ApiException.unauthorized("malformed token subject");
        }
        User user = userRepository.findByUuid(uuid)
                .orElseThrow(() -> ApiException.unauthorized("user not found"));
        return issueAuthResponse(user);
    }

    public void logout(String accessToken) {
        try {
            Claims claims = tokenProvider.verify(accessToken);
            tokenProvider.revoke(claims);
        } catch (Exception ex) {
            // Already-invalid token — no-op so logout stays idempotent.
            log.debug("logout_token_already_invalid");
        }
    }

    // --- Internal helpers ---

    private Optional<User> lookupForLogin(LoginRequest req) {
        if (req.phone() != null && !req.phone().isBlank()) {
            return userRepository.findByPhone(req.phone());
        }
        if (req.email() != null && !req.email().isBlank()) {
            return userRepository.findByEmail(req.email());
        }
        return Optional.empty();
    }

    private AuthResponse issueAuthResponse(User user) {
        UserPrincipal principal = UserPrincipal.from(user);
        String access = tokenProvider.issueAccess(principal);
        String refresh = tokenProvider.issueRefresh(principal);
        // Access TTL is configured globally; we just expose seconds for the client.
        long expiresIn = 60L * 120L; // 2h matches application.yml default.
        return new AuthResponse(access, refresh, expiresIn, UserResponse.from(user));
    }
}
