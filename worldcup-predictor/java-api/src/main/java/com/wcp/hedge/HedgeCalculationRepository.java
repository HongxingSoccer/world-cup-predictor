package com.wcp.hedge;

import com.wcp.hedge.entity.HedgeCalculationEntity;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface HedgeCalculationRepository extends JpaRepository<HedgeCalculationEntity, Long> {

    List<HedgeCalculationEntity> findByScenarioIdOrderByIdAsc(Long scenarioId);

    /** Used by {@code POST /scenarios/{id}/recalc} to clear stale rows. */
    void deleteByScenarioId(Long scenarioId);
}
