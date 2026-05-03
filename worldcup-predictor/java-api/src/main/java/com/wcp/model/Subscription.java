package com.wcp.model;

import jakarta.persistence.*;
import java.time.Instant;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

/** Per-user paid access window. One row per (re-)subscription event. */
@Entity
@Table(name = "subscriptions")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder(toBuilder = true)
public class Subscription {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false)
    private Long userId;

    @Column(length = 20, nullable = false)
    private String tier;

    @Column(name = "plan_type", length = 20, nullable = false)
    private String planType;

    @Setter
    @Column(length = 20, nullable = false)
    @Builder.Default
    private String status = "active";

    @Column(name = "price_cny", nullable = false)
    private Integer priceCny;

    @Column(name = "started_at", nullable = false)
    private Instant startedAt;

    @Setter
    @Column(name = "expires_at", nullable = false)
    private Instant expiresAt;

    @Setter
    @Column(name = "auto_renew", nullable = false)
    @Builder.Default
    private boolean autoRenew = false;

    @Column(name = "payment_id")
    private Long paymentId;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    public boolean isActiveAt(Instant ts) {
        return "active".equals(status) && ts.isBefore(expiresAt);
    }
}
