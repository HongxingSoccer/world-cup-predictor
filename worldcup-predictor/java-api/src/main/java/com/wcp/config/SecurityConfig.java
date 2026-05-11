package com.wcp.config;

import com.wcp.security.JwtAuthFilter;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;

/**
 * Security wiring: stateless JWT auth + path-level allow-list.
 *
 * <p>Public paths (auth, public match data, share-link redirect, swagger,
 * health) → permitAll. Everything else requires a valid access token, with
 * {@code /api/v1/admin/**} additionally restricted to ROLE_ADMIN.
 */
@Configuration
@EnableMethodSecurity
@RequiredArgsConstructor
public class SecurityConfig {

    private final JwtAuthFilter jwtAuthFilter;
    private final UrlBasedCorsConfigurationSource corsConfigurationSource;

    @Bean
    public PasswordEncoder passwordEncoder() {
        // Cost 12 per project standards (§12.1).
        return new BCryptPasswordEncoder(12);
    }

    @Bean
    public SecurityFilterChain securityFilterChain(HttpSecurity http) throws Exception {
        http
                .csrf(AbstractHttpConfigurer::disable)
                .cors(cors -> cors.configurationSource(corsConfigurationSource))
                .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(auth -> auth
                        // --- Public ---
                        .requestMatchers("/api/v1/auth/**").permitAll()
                        .requestMatchers("/api/v1/track-record/**").permitAll()
                        .requestMatchers(HttpMethod.GET, "/api/v1/matches/today").permitAll()
                        .requestMatchers(HttpMethod.GET, "/api/v1/matches/upcoming").permitAll()
                        .requestMatchers(HttpMethod.GET, "/api/v1/matches/{id:[0-9]+}").permitAll()
                        .requestMatchers(HttpMethod.GET, "/api/v1/matches/{id:[0-9]+}/prediction").permitAll()
                        .requestMatchers(HttpMethod.GET, "/api/v1/matches/{id:[0-9]+}/odds-analysis").permitAll()
                        .requestMatchers(HttpMethod.GET, "/api/v1/matches/{id:[0-9]+}/related").permitAll()
                        .requestMatchers(HttpMethod.GET, "/api/v1/matches/{id:[0-9]+}/report").permitAll()
                        .requestMatchers(HttpMethod.GET, "/api/v1/competitions/**").permitAll()
                        // Pricing catalogue is the unauthenticated subscribe-page entry point.
                        .requestMatchers(HttpMethod.GET, "/api/v1/subscriptions/plans").permitAll()
                        .requestMatchers("/s/**").permitAll()
                        .requestMatchers(HttpMethod.POST, "/api/v1/payments/callback/**").permitAll()
                        // `/actuator/prometheus` is open so the in-cluster
                        // Prometheus scraper can hit it without a JWT. In
                        // EKS we'll restrict access at the NetworkPolicy /
                        // SG layer rather than via Spring Security.
                        .requestMatchers(
                                "/actuator/health",
                                "/actuator/info",
                                "/actuator/prometheus",
                                "/actuator/metrics"
                        ).permitAll()
                        .requestMatchers("/swagger-ui/**", "/swagger-ui.html", "/api-docs/**").permitAll()

                        // --- Admin ---
                        .requestMatchers("/api/v1/admin/**").hasRole("ADMIN")

                        // --- Authenticated ---
                        .anyRequest().authenticated()
                )
                .addFilterBefore(jwtAuthFilter, UsernamePasswordAuthenticationFilter.class);

        return http.build();
    }
}
