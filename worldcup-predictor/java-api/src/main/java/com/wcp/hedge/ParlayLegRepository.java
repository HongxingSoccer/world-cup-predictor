package com.wcp.hedge;

import com.wcp.hedge.entity.ParlayLegEntity;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface ParlayLegRepository extends JpaRepository<ParlayLegEntity, Long> {

    List<ParlayLegEntity> findByScenarioIdOrderByLegOrderAsc(Long scenarioId);
}
