package com.wcp.positions.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

/**
 * Maps to {@code user_positions} (Alembic 0007_phase4_m9_positions).
 *
 * <p>Schema reference: {@code docs/M9_5_live_hedging_flow.md} §1.
 */
@Entity
@Table(name = "user_positions")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder(toBuilder = true)
public class PositionEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false)
    private Long userId;

    @Column(name = "match_id", nullable = false)
    private Long matchId;

    @Column(nullable = false, length = 50)
    private String platform;

    @Column(nullable = false, length = 30)
    private String market;

    @Column(nullable = false, length = 30)
    private String outcome;

    @Column(nullable = false, precision = 12, scale = 2)
    private BigDecimal stake;

    @Column(nullable = false, precision = 8, scale = 3)
    private BigDecimal odds;

    @Column(name = "placed_at", nullable = false)
    private OffsetDateTime placedAt;

    @Setter
    @Column(nullable = false, length = 20)
    @Builder.Default
    private String status = "active";

    @Setter
    @Column(columnDefinition = "TEXT")
    private String notes;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at", nullable = false)
    private OffsetDateTime updatedAt;

    @Setter
    @Column(name = "last_alert_at")
    private OffsetDateTime lastAlertAt;

    @Setter
    @Column(name = "settlement_pnl", precision = 12, scale = 2)
    private BigDecimal settlementPnl;
}
