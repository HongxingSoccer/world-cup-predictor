package com.wcp.dto.request;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

/**
 * Registration payload. At least one of {@code phone} / {@code email} must be
 * provided + a password (BCrypt-hashed server-side). Phone OTP and email
 * OTP arrive in Phase 3.5.
 */
public record RegisterRequest(
        @Pattern(regexp = "^1[3-9]\\d{9}$", message = "phone must be a Mainland China mobile number")
        String phone,
        @Email
        String email,
        @Size(min = 8, max = 128)
        String password,
        @Size(max = 50)
        String nickname
) {}
