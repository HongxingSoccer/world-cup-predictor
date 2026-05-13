package com.wcp.hedge.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
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
 * Maps to {@code hedge_calculations} table (Alembic 0006_phase4_m9_hedging).
 *
 * <p>Schema reference: {@code docs/M9_hedging_module_design.md} §3.3.
 * The {@code model_assessment} column is GAP 1 in the design — added so
 * history reads don't have to re-invoke the advisor.
 */
@Entity
@Table(name = "hedge_calculations")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder(toBuilder = true)
public class HedgeCalculationEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "scenario_id", nullable = false)
    private HedgeScenarioEntity scenario;

    @Column(name = "hedge_outcome", length = 30, nullable = false)
    private String hedgeOutcome;

    @Column(name = "hedge_odds", precision = 8, scale = 3, nullable = false)
    private BigDecimal hedgeOdds;

    @Column(name = "hedge_bookmaker", length = 50, nullable = false)
    private String hedgeBookmaker;

    @Column(name = "hedge_stake", precision = 12, scale = 2, nullable = false)
    private BigDecimal hedgeStake;

    @Column(name = "profit_if_original_wins", precision = 12, scale = 2, nullable = false)
    private BigDecimal profitIfOriginalWins;

    @Column(name = "profit_if_hedge_wins", precision = 12, scale = 2, nullable = false)
    private BigDecimal profitIfHedgeWins;

    @Column(name = "max_loss", precision = 12, scale = 2, nullable = false)
    private BigDecimal maxLoss;

    @Column(name = "guaranteed_profit", precision = 12, scale = 2)
    private BigDecimal guaranteedProfit;

    @Column(name = "ev_of_hedge", precision = 8, scale = 4)
    private BigDecimal evOfHedge;

    @Column(name = "model_prob_hedge", precision = 5, scale = 4)
    private BigDecimal modelProbHedge;

    /** GAP 1 — advisor verdict persisted alongside the calculation. */
    @Column(name = "model_assessment", length = 50)
    private String modelAssessment;

    @CreationTimestamp
    @Column(name = "calculated_at", nullable = false, updatable = false)
    private OffsetDateTime calculatedAt;
}
