package com.wcp.hedge.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.OneToOne;
import jakarta.persistence.Table;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.CreationTimestamp;

/**
 * Maps to {@code hedge_results} table (Alembic 0006_phase4_m9_hedging).
 *
 * <p>Schema reference: {@code docs/M9_hedging_module_design.md} §3.4.
 * Settlement-time fields (GAP 5): {@code would_have_pnl} and
 * {@code hedge_value_added} are persisted by the settlement job.
 */
@Entity
@Table(name = "hedge_results")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder(toBuilder = true)
public class HedgeResultEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @OneToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "scenario_id", nullable = false, unique = true)
    private HedgeScenarioEntity scenario;

    @Column(name = "actual_outcome", length = 30, nullable = false)
    private String actualOutcome;

    @Column(name = "original_pnl", precision = 12, scale = 2, nullable = false)
    private BigDecimal originalPnl;

    @Column(name = "hedge_pnl", precision = 12, scale = 2, nullable = false)
    private BigDecimal hedgePnl;

    @Column(name = "total_pnl", precision = 12, scale = 2, nullable = false)
    private BigDecimal totalPnl;

    @Column(name = "would_have_pnl", precision = 12, scale = 2, nullable = false)
    private BigDecimal wouldHavePnl;

    @Column(name = "hedge_value_added", precision = 12, scale = 2, nullable = false)
    private BigDecimal hedgeValueAdded;

    @CreationTimestamp
    @Column(name = "settled_at", nullable = false, updatable = false)
    private OffsetDateTime settledAt;
}
