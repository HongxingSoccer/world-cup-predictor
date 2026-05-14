package com.wcp.arbitrage;

import com.wcp.arbitrage.entity.ArbWatchlistEntity;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface ArbWatchlistRepository extends JpaRepository<ArbWatchlistEntity, Long> {

    List<ArbWatchlistEntity> findByUserIdOrderByCreatedAtDesc(Long userId);

    Optional<ArbWatchlistEntity> findByIdAndUserId(Long id, Long userId);
}
