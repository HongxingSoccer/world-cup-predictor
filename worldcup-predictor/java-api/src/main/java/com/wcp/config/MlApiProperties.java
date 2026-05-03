package com.wcp.config;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Connection settings for the Python ML FastAPI service.
 *
 * <p>{@code base-url} is typically {@code http://ml-api:8000} inside
 * docker-compose; {@code api-key} (when set) is forwarded as the
 * {@code X-API-Key} header on every outbound request.
 */
@ConfigurationProperties(prefix = "wcp.ml-api")
public record MlApiProperties(
        @NotBlank String baseUrl,
        String apiKey,
        @Min(100) int connectTimeoutMs,
        @Min(100) int readTimeoutMs
) {}
