package com.wcp.dto.response;

/** Auth token bundle returned by /register, /login, /refresh. */
public record AuthResponse(
        String accessToken,
        String refreshToken,
        long expiresInSeconds,
        UserResponse user
) {}
