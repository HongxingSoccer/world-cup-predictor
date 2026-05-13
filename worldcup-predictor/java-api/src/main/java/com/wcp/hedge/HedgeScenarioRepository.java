package com.wcp.hedge;

import com.wcp.hedge.entity.HedgeScenarioEntity;
import java.util.Optional;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface HedgeScenarioRepository extends JpaRepository<HedgeScenarioEntity, Long> {

    Page<HedgeScenarioEntity> findByUserIdOrderByCreatedAtDesc(Long userId, Pageable pageable);

    /** Eager-load calculations + legs for the detail endpoint. */
    @EntityGraph(attributePaths = {"calculations", "legs"})
    Optional<HedgeScenarioEntity> findWithChildrenById(Long id);

    Optional<HedgeScenarioEntity> findByIdAndUserId(Long id, Long userId);
}
