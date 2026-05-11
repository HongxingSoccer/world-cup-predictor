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
 * @param stripe  Stripe payment integration credentials (optional — when
 *                {@code secretKey} is blank the channel is treated as
 *                un-configured and orders default back to the dev stub).
 */
@Validated
@ConfigurationProperties(prefix = "wcp")
public record WcpProperties(
        Jwt jwt,
        Share share,
        Cors cors,
        Stripe stripe,
        Payments payments
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

    /**
     * Optional fields — empty defaults so the app still boots without
     * Stripe credentials configured (Phase-3.5 dev environments).
     */
    public record Stripe(
            String secretKey,
            String webhookSecret,
            String successUrl,
            String cancelUrl
    ) {
        public boolean isConfigured() {
            return secretKey != null && !secretKey.isBlank();
        }
    }

    /**
     * Toggles for payment channels whose real SDK is not yet integrated.
     * {@code enableCnChannels} unlocks the Alipay / WeChat code paths
     * (currently stub) — leave it FALSE in any environment that's exposed
     * to the public internet, otherwise an attacker can replay forged
     * callbacks and flip a Payment row to {@code paid} without spending
     * a yuan. Stripe is unaffected — it has a real signature check.
     */
    public record Payments(boolean enableCnChannels) {}
}
