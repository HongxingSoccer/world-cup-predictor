package com.wcp.security;

import com.wcp.config.WcpProperties;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.Jws;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import jakarta.annotation.PostConstruct;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyFactory;
import java.security.PrivateKey;
import java.security.PublicKey;
import java.security.spec.PKCS8EncodedKeySpec;
import java.security.spec.X509EncodedKeySpec;
import java.time.Duration;
import java.time.Instant;
import java.util.Base64;
import java.util.Date;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Component;

/**
 * RS256 JWT issuer + verifier.
 *
 * <p>Loads the RSA key pair from the paths configured under
 * {@code wcp.jwt.*}. Public key is exposed via {@link #publicKey()} so the
 * front-end can verify tokens client-side (Phase 4 deliverable).
 *
 * <p>Logout / password-change blacklists go through Redis under
 * {@code jwt:blacklist:<jti>}; the TTL matches the token's remaining
 * validity so the entry self-expires once it can no longer cause harm.
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class JwtTokenProvider {

    private static final String CLAIM_ROLE = "role";
    private static final String CLAIM_TIER = "tier";
    private static final String CLAIM_TYPE = "typ";
    private static final String TYPE_ACCESS = "access";
    private static final String TYPE_REFRESH = "refresh";
    private static final String BLACKLIST_KEY_PREFIX = "jwt:blacklist:";

    private final WcpProperties wcpProperties;
    private final RedisTemplate<String, Object> redisTemplate;

    private PrivateKey privateKey;
    private PublicKey publicKey;

    @PostConstruct
    void loadKeys() throws IOException {
        WcpProperties.Jwt cfg = wcpProperties.jwt();
        try {
            this.privateKey = readPrivateKey(Path.of(cfg.privateKeyPath()));
            this.publicKey = readPublicKey(Path.of(cfg.publicKeyPath()));
        } catch (Exception ex) {
            throw new IllegalStateException(
                    "Failed to load JWT keys at " + cfg.privateKeyPath() + " / " + cfg.publicKeyPath(),
                    ex);
        }
        log.info("JWT keys loaded from {}", cfg.privateKeyPath());
    }

    public String issueAccess(UserPrincipal principal) {
        return issue(principal, TYPE_ACCESS,
                Duration.ofMinutes(wcpProperties.jwt().accessTokenTtlMinutes()));
    }

    public String issueRefresh(UserPrincipal principal) {
        return issue(principal, TYPE_REFRESH,
                Duration.ofDays(wcpProperties.jwt().refreshTokenTtlDays()));
    }

    /** Verify a token + check the blacklist.
     *
     * <p>Throws {@link JwtException} when the signature is invalid, the
     * issuer mismatches, or the token's jti is in the Redis blacklist.
     *
     * <p>Blacklist-lookup failures (e.g. Redis unreachable) are
     * <strong>fail-open</strong>: the RSA signature already verified, so
     * downing the entire API on a Redis blip would be worse than honouring
     * a still-valid token. Production ops alerts cover the case where the
     * blacklist isn't enforceable for an extended period.
     */
    public Claims verify(String token) {
        Jws<Claims> jws = Jwts.parser()
            .verifyWith(publicKey)
            .requireIssuer(wcpProperties.jwt().issuer())
            .build()
            .parseSignedClaims(token);
        Claims claims = jws.getPayload();
        try {
            if (Boolean.TRUE.equals(redisTemplate.hasKey(BLACKLIST_KEY_PREFIX + claims.getId()))) {
                throw new JwtException("token has been revoked");
            }
        } catch (JwtException jwtException) {
            throw jwtException;
        } catch (Exception redisException) {
            log.warn("jwt_blacklist_unavailable error={}", redisException.getMessage());
        }
        return claims;
    }

    /** Add the token's jti to the Redis blacklist. */
    public void revoke(Claims claims) {
        Date exp = claims.getExpiration();
        long ttlMs = exp != null ? Math.max(0, exp.getTime() - System.currentTimeMillis()) : 0L;
        if (ttlMs <= 0) {
            return;
        }
        redisTemplate.opsForValue().set(
                BLACKLIST_KEY_PREFIX + claims.getId(),
                "revoked",
                ttlMs,
                java.util.concurrent.TimeUnit.MILLISECONDS
        );
    }

    public PublicKey publicKey() {
        return publicKey;
    }

    public boolean isAccessToken(Claims claims) {
        return TYPE_ACCESS.equals(claims.get(CLAIM_TYPE, String.class));
    }

    public boolean isRefreshToken(Claims claims) {
        return TYPE_REFRESH.equals(claims.get(CLAIM_TYPE, String.class));
    }

    // --- Internal -----------------------------------------------------

    private String issue(UserPrincipal principal, String type, Duration ttl) {
        Instant now = Instant.now();
        return Jwts.builder()
                .id(UUID.randomUUID().toString())
                .issuer(wcpProperties.jwt().issuer())
                .subject(principal.uuid().toString())
                .claim(CLAIM_ROLE, principal.role())
                .claim(CLAIM_TIER, principal.subscriptionTier().wireValue())
                .claim(CLAIM_TYPE, type)
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plus(ttl)))
                .signWith(privateKey, Jwts.SIG.RS256)
                .compact();
    }

    private static PrivateKey readPrivateKey(Path path) throws Exception {
        byte[] decoded = pemBody(Files.readString(path), "PRIVATE KEY");
        return KeyFactory.getInstance("RSA").generatePrivate(new PKCS8EncodedKeySpec(decoded));
    }

    private static PublicKey readPublicKey(Path path) throws Exception {
        byte[] decoded = pemBody(Files.readString(path), "PUBLIC KEY");
        return KeyFactory.getInstance("RSA").generatePublic(new X509EncodedKeySpec(decoded));
    }

    private static byte[] pemBody(String pem, String label) {
        String body = pem
                .replace("-----BEGIN " + label + "-----", "")
                .replace("-----END " + label + "-----", "")
                .replaceAll("\\s+", "");
        return Base64.getDecoder().decode(body);
    }
}
