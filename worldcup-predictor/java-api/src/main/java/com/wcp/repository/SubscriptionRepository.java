package com.wcp.repository;

import com.wcp.model.Subscription;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface SubscriptionRepository extends JpaRepository<Subscription, Long> {

    @Query(
            "SELECT s FROM Subscription s "
                    + "WHERE s.userId = :userId AND s.status = 'active' AND s.expiresAt > :now "
                    + "ORDER BY s.expiresAt DESC"
    )
    Optional<Subscription> findActive(@Param("userId") Long userId, @Param("now") Instant now);

    List<Subscription> findByUserIdOrderByCreatedAtDesc(Long userId);
}
