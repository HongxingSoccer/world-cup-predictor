package com.wcp.config;

import java.util.Arrays;
import java.util.List;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

/**
 * CORS allow-list. Driven by {@code wcp.cors.allowed-origins} (comma-separated)
 * so deployments can swap the value via env without rebuilding.
 */
@Configuration
public class CorsConfig {

    @Bean
    public UrlBasedCorsConfigurationSource corsConfigurationSource(WcpProperties wcpProperties) {
        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        CorsConfiguration config = new CorsConfiguration();

        List<String> origins = Arrays.stream(wcpProperties.cors().allowedOrigins().split(","))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .toList();
        if (origins.size() == 1 && "*".equals(origins.get(0))) {
            config.addAllowedOriginPattern("*");
        } else {
            origins.forEach(config::addAllowedOrigin);
            config.setAllowCredentials(true);
        }
        config.addAllowedMethod("*");
        config.addAllowedHeader("*");

        source.registerCorsConfiguration("/**", config);
        return source;
    }
}
