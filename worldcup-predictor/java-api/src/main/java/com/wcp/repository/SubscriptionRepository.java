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

    /**
     * Active paid windows ordered longest-future-first. Returns a list (not
     * Optional) because a user can legitimately stack subscriptions — e.g.
     * a still-running monthly when a World-Cup pass is purchased — and the
     * old single-result version threw {@code IncorrectResultSizeDataAccessException}
     * the moment two active rows existed. Callers that want the dominant
     * window should take the first element.
     */
    @Query(
            "SELECT s FROM Subscription s "
                    + "WHERE s.userId = :userId AND s.status = 'active' AND s.expiresAt > :now "
                    + "ORDER BY s.expiresAt DESC"
    )
    List<Subscription> findActiveWindows(@Param("userId") Long userId, @Param("now") Instant now);

    /** Convenience: the dominant (longest-running) active subscription, if any. */
    default Optional<Subscription> findActive(Long userId, Instant now) {
        return findActiveWindows(userId, now).stream().findFirst();
    }

    List<Subscription> findByUserIdOrderByCreatedAtDesc(Long userId);
}
