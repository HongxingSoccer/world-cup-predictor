package com.wcp.model;

import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

/**
 * Core user identity entity. Mirrors the Python {@code users} table.
 *
 * <p>Setters are kept narrow on purpose — most fields mutate via service-level
 * helpers (e.g. {@code recordLogin}) so business rules around state changes
 * stay collocated with the entity rather than scattered across controllers.
 */
@Entity
@Table(name = "users")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder(toBuilder = true)
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, unique = true, updatable = false)
    private UUID uuid;

    @Column(length = 20)
    private String phone;

    @Column(length = 200)
    private String email;

    @Column(name = "password_hash", length = 255)
    private String passwordHash;

    @Setter
    @Column(length = 50)
    private String nickname;

    @Setter
    @Column(name = "avatar_url", columnDefinition = "TEXT")
    private String avatarUrl;

    @Column(name = "subscription_tier", length = 20, nullable = false)
    @Builder.Default
    private String subscriptionTier = "free";

    @Column(name = "subscription_expires")
    private Instant subscriptionExpires;

    @Setter
    @Column(length = 10, nullable = false)
    @Builder.Default
    private String locale = "zh-CN";

    @Setter
    @Column(length = 50, nullable = false)
    @Builder.Default
    private String timezone = "Asia/Shanghai";

    @Column(name = "last_login_at")
    private Instant lastLoginAt;

    @Column(name = "is_active", nullable = false)
    @Builder.Default
    private boolean active = true;

    @Column(length = 20, nullable = false)
    @Builder.Default
    private String role = "user";

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    // --- Business helpers ---

    public boolean isAdmin() {
        return "admin".equals(this.role);
    }

    /** Apply a successful login. Bumps {@code lastLoginAt} only. */
    public void recordLogin(Instant when) {
        this.lastLoginAt = when;
    }

    /** Activate or refresh a paid tier window. */
    public void grantSubscription(String tier, Instant expiresAt) {
        this.subscriptionTier = tier;
        this.subscriptionExpires = expiresAt;
    }

    /** Revert to the free tier (used by refunds + expiry sweep). */
    public void revertToFree() {
        this.subscriptionTier = "free";
        this.subscriptionExpires = null;
    }
}
