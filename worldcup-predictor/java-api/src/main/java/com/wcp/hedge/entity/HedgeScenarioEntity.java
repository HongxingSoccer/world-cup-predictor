package com.wcp.hedge.entity;

import jakarta.persistence.CascadeType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.OneToMany;
import jakarta.persistence.OneToOne;
import jakarta.persistence.OrderBy;
import jakarta.persistence.Table;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.List;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

/**
 * Maps to {@code hedge_scenarios} table (Alembic 0006_phase4_m9_hedging).
 *
 * <p>Schema reference: {@code docs/M9_hedging_module_design.md} §3.2.
 * Constraints are enforced at the DB level (CHECK constraints) so the
 * entity layer does not duplicate validation rules.
 */
@Entity
@Table(name = "hedge_scenarios")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder(toBuilder = true)
public class HedgeScenarioEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false)
    private Long userId;

    @Column(name = "scenario_type", length = 20, nullable = false)
    private String scenarioType;

    @Column(name = "match_id")
    private Long matchId;

    @Column(name = "original_stake", precision = 12, scale = 2, nullable = false)
    private BigDecimal originalStake;

    @Column(name = "original_odds", precision = 8, scale = 3, nullable = false)
    private BigDecimal originalOdds;

    @Column(name = "original_outcome", length = 30, nullable = false)
    private String originalOutcome;

    @Column(name = "original_market", length = 30, nullable = false)
    private String originalMarket;

    @Column(name = "hedge_mode", length = 20, nullable = false)
    private String hedgeMode;

    @Column(name = "hedge_ratio", precision = 4, scale = 3, nullable = false)
    private BigDecimal hedgeRatio;

    @Setter
    @Column(length = 20, nullable = false)
    @Builder.Default
    private String status = "active";

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at", nullable = false)
    private OffsetDateTime updatedAt;

    @OneToMany(
            mappedBy = "scenario",
            cascade = CascadeType.ALL,
            orphanRemoval = true,
            fetch = FetchType.LAZY)
    @OrderBy("id ASC")
    @Builder.Default
    private List<HedgeCalculationEntity> calculations = new ArrayList<>();

    @OneToOne(
            mappedBy = "scenario",
            cascade = CascadeType.ALL,
            orphanRemoval = true,
            fetch = FetchType.LAZY)
    private HedgeResultEntity result;

    @OneToMany(
            mappedBy = "scenario",
            cascade = CascadeType.ALL,
            orphanRemoval = true,
            fetch = FetchType.LAZY)
    @OrderBy("legOrder ASC")
    @Builder.Default
    private List<ParlayLegEntity> legs = new ArrayList<>();
}
