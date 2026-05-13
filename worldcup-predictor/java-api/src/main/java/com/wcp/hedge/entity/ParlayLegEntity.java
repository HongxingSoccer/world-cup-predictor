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
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

/**
 * Maps to {@code parlay_legs} table (Alembic 0006_phase4_m9_hedging).
 *
 * <p>Schema reference: {@code docs/M9_hedging_module_design.md} §3.5.
 * Each row is one leg of a parlay scenario; ordering preserved via
 * {@code legOrder} (1-based).
 */
@Entity
@Table(name = "parlay_legs")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder(toBuilder = true)
public class ParlayLegEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "scenario_id", nullable = false)
    private HedgeScenarioEntity scenario;

    @Column(name = "leg_order", nullable = false)
    private Short legOrder;

    @Column(name = "match_id", nullable = false)
    private Long matchId;

    @Column(length = 30, nullable = false)
    private String outcome;

    @Column(precision = 8, scale = 3, nullable = false)
    private BigDecimal odds;

    @Setter
    @Column(name = "is_settled", nullable = false)
    @Builder.Default
    private Boolean isSettled = false;

    @Setter
    @Column(name = "is_won")
    private Boolean isWon;
}
