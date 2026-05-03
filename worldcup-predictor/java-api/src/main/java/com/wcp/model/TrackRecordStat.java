package com.wcp.model;

import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.UpdateTimestamp;

/** Denormalised aggregate row for the public scoreboard. Keyed by (statType, period). */
@Entity
@Table(name = "track_record_stats")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
public class TrackRecordStat {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "stat_type", length = 30, nullable = false)
    private String statType;

    @Column(length = 20, nullable = false)
    private String period;

    @Column(name = "total_predictions", nullable = false)
    private Integer totalPredictions;

    @Column(nullable = false)
    private Integer hits;

    @Column(name = "hit_rate", nullable = false, precision = 5, scale = 4)
    private BigDecimal hitRate;

    @Column(name = "total_pnl_units", nullable = false, precision = 10, scale = 4)
    private BigDecimal totalPnlUnits;

    @Column(nullable = false, precision = 6, scale = 4)
    private BigDecimal roi;

    @Column(name = "current_streak", nullable = false)
    private Integer currentStreak;

    @Column(name = "best_streak", nullable = false)
    private Integer bestStreak;

    @UpdateTimestamp
    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;
}
