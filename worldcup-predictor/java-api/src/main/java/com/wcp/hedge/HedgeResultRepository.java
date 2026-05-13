package com.wcp.hedge;

import com.wcp.hedge.entity.HedgeResultEntity;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface HedgeResultRepository extends JpaRepository<HedgeResultEntity, Long> {

    Optional<HedgeResultEntity> findByScenarioId(Long scenarioId);

    /** Settled scenarios for a user, most-recent first. */
    @Query("""
        SELECT r FROM HedgeResultEntity r
        WHERE r.scenario.userId = :userId
        ORDER BY r.settledAt DESC
        """)
    List<HedgeResultEntity> findByUserId(@Param("userId") Long userId);

    /** Sums for the /stats endpoint — one row per user. */
    @Query("""
        SELECT
            COUNT(r),
            COALESCE(SUM(r.totalPnl), 0),
            COALESCE(SUM(r.wouldHavePnl), 0),
            COALESCE(SUM(r.hedgeValueAdded), 0),
            SUM(CASE WHEN r.totalPnl > 0 THEN 1 ELSE 0 END)
        FROM HedgeResultEntity r
        WHERE r.scenario.userId = :userId
        """)
    Object[] aggregateForUser(@Param("userId") Long userId);
}
