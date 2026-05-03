package com.wcp.config;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

/**
 * Top-level configuration binding for {@code wcp.*} settings.
 *
 * @param jwt     JWT signing / verification config (RS256 key paths + TTLs).
 * @param share   Outbound share-link prefix (e.g. https://wcp.app/s/).
 */
@Validated
@ConfigurationProperties(prefix = "wcp")
public record WcpProperties(
        Jwt jwt,
        Share share,
        Cors cors
) {

    public record Jwt(
            @NotBlank String privateKeyPath,
            @NotBlank String publicKeyPath,
            @Min(1) int accessTokenTtlMinutes,
            @Min(1) int refreshTokenTtlDays,
            @NotBlank String issuer
    ) {}

    public record Share(@NotBlank String baseUrl) {}

    public record Cors(@NotBlank String allowedOrigins) {}
}
