package com.wcp.security;

import com.wcp.model.User;
import com.wcp.repository.UserRepository;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.lang.NonNull;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.authentication.WebAuthenticationDetailsSource;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

/**
 * Per-request JWT validation filter.
 *
 * <p>Reads {@code Authorization: Bearer <token>}. On a valid access token,
 * loads the user and pushes a {@link UserPrincipal} onto the security
 * context. Invalid / expired / blacklisted tokens are silently ignored —
 * the request still continues and the {@code SecurityConfig} chain decides
 * whether the path is public.
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class JwtAuthFilter extends OncePerRequestFilter {

    private static final String HEADER = "Authorization";
    private static final String PREFIX = "Bearer ";

    private final JwtTokenProvider tokenProvider;
    private final UserRepository userRepository;

    @Override
    protected void doFilterInternal(
            @NonNull HttpServletRequest request,
            @NonNull HttpServletResponse response,
            @NonNull FilterChain chain
    ) throws ServletException, IOException {
        String token = extractToken(request);
        if (token != null) {
            try {
                Claims claims = tokenProvider.verify(token);
                if (tokenProvider.isAccessToken(claims)) {
                    authenticate(claims, request);
                }
            } catch (JwtException ex) {
                log.debug("jwt_rejected reason={}", ex.getMessage());
                SecurityContextHolder.clearContext();
            }
        }
        chain.doFilter(request, response);
    }

    private void authenticate(Claims claims, HttpServletRequest request) {
        UUID uuid;
        try {
            uuid = UUID.fromString(claims.getSubject());
        } catch (IllegalArgumentException ex) {
            return;
        }
        User user = userRepository.findByUuid(uuid).orElse(null);
        if (user == null || !user.isActive()) {
            return;
        }

        UserPrincipal principal = UserPrincipal.from(user);
        UsernamePasswordAuthenticationToken auth =
                new UsernamePasswordAuthenticationToken(principal, null, principal.getAuthorities());
        auth.setDetails(new WebAuthenticationDetailsSource().buildDetails(request));
        SecurityContextHolder.getContext().setAuthentication(auth);
    }

    private static String extractToken(HttpServletRequest request) {
        String header = request.getHeader(HEADER);
        if (header == null || !header.startsWith(PREFIX)) {
            return null;
        }
        return header.substring(PREFIX.length()).trim();
    }
}
