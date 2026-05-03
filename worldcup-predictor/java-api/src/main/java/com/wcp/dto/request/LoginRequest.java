package com.wcp.dto.request;

import jakarta.validation.constraints.NotBlank;

/** Email-+-password login. Phone-OTP login lives behind a separate endpoint. */
public record LoginRequest(
        String phone,
        String email,
        @NotBlank String password
) {}
