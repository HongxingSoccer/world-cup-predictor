package com.wcp.positions;

import com.wcp.positions.entity.PositionEntity;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface PositionRepository extends JpaRepository<PositionEntity, Long> {

    List<PositionEntity> findByUserIdOrderByCreatedAtDesc(Long userId);

    List<PositionEntity> findByUserIdAndStatusOrderByCreatedAtDesc(
            Long userId, String status);

    Optional<PositionEntity> findByIdAndUserId(Long id, Long userId);
}
