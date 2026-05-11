package com.wcp.repository;

import static org.assertj.core.api.Assertions.assertThat;

import com.wcp.model.Subscription;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase.Replace;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.test.context.ActiveProfiles;

/**
 * Pins the chokepoint query the rest of the system relies on to know
 * whether a user is paid or not. The custom JPQL on
 * {@link SubscriptionRepository#findActive(Long, Instant)} has three
 * filters (status, expires_at, ordering) — any one breaking silently
 * downgrades a paid user to free.
 */
@DataJpaTest
@AutoConfigureTestDatabase(replace = Replace.NONE)
@ActiveProfiles("test")
class SubscriptionRepositoryTest {

    @Autowired private SubscriptionRepository subscriptions;

    private static Subscription sub(long userId, String status, Instant expiresAt) {
        return Subscription.builder()
                .userId(userId)
                .tier("premium")
                .planType("monthly")
                .status(status)
                .priceCny(14393)
                .startedAt(Instant.now().minus(Duration.ofDays(1)))
                .expiresAt(expiresAt)
                .autoRenew(false)
                .build();
    }

    @Test
    @DisplayName("findActive returns empty when the user has no subscriptions")
    void emptyUser() {
        assertThat(subscriptions.findActive(999L, Instant.now())).isEmpty();
    }

    @Test
    @DisplayName("findActive returns the subscription when it's active and not yet expired")
    void happyPath() {
        Instant future = Instant.now().plus(Duration.ofDays(7));
        Subscription saved = subscriptions.save(sub(1L, "active", future));

        Optional<Subscription> hit = subscriptions.findActive(1L, Instant.now());

        assertThat(hit).isPresent();
        assertThat(hit.get().getId()).isEqualTo(saved.getId());
    }

    @Test
    @DisplayName("findActive ignores cancelled subscriptions even if expires_at is in the future")
    void cancelledExcluded() {
        Instant future = Instant.now().plus(Duration.ofDays(7));
        subscriptions.save(sub(1L, "cancelled", future));

        assertThat(subscriptions.findActive(1L, Instant.now())).isEmpty();
    }

    @Test
    @DisplayName("findActive ignores expired subscriptions even if status is still 'active'")
    void expiredExcluded() {
        Instant past = Instant.now().minus(Duration.ofDays(1));
        subscriptions.save(sub(1L, "active", past));

        assertThat(subscriptions.findActive(1L, Instant.now())).isEmpty();
    }

    @Test
    @DisplayName("findActive returns the subscription with the latest expires_at when multiple are valid")
    void multipleActivePicksLatestExpiry() {
        // Stacking two paid subscriptions can happen if a user buys a
        // World-Cup pass while a monthly is still running. The query must
        // return the one that lasts longest so JWT tier claims reflect the
        // window the user actually has.
        Subscription shorter = subscriptions.save(
                sub(1L, "active", Instant.now().plus(Duration.ofDays(7)))
        );
        Subscription longer = subscriptions.save(
                sub(1L, "active", Instant.now().plus(Duration.ofDays(60)))
        );

        Optional<Subscription> hit = subscriptions.findActive(1L, Instant.now());

        assertThat(hit).isPresent();
        assertThat(hit.get().getId()).isEqualTo(longer.getId());
        assertThat(hit.get().getId()).isNotEqualTo(shorter.getId());
    }

    @Test
    @DisplayName("findActive only returns the requested user's subscriptions, never another user's")
    void userScoping() {
        // Defensive: a copy-paste bug that strips the user_id filter would
        // hand any user the first active subscription found, an obvious
        // tier-leak. Pin it.
        subscriptions.save(sub(7L, "active", Instant.now().plus(Duration.ofDays(30))));
        subscriptions.save(sub(8L, "active", Instant.now().plus(Duration.ofDays(30))));

        Optional<Subscription> hit = subscriptions.findActive(7L, Instant.now());

        assertThat(hit).isPresent();
        assertThat(hit.get().getUserId()).isEqualTo(7L);
    }

    @Test
    @DisplayName("findByUserIdOrderByCreatedAtDesc returns history newest-first across statuses")
    void historyOrderedNewestFirst() {
        // History view is allowed to include cancelled / expired rows — the
        // ordering is what matters for the profile-page timeline.
        Subscription s1 = subscriptions.save(
                sub(2L, "expired", Instant.now().minus(Duration.ofDays(60)))
        );
        try { Thread.sleep(5); } catch (InterruptedException ignored) {}
        Subscription s2 = subscriptions.save(
                sub(2L, "active", Instant.now().plus(Duration.ofDays(30)))
        );

        List<Subscription> out = subscriptions.findByUserIdOrderByCreatedAtDesc(2L);

        assertThat(out).hasSize(2);
        // Newest first — s2 was inserted last, so it leads.
        assertThat(out.get(0).getId()).isEqualTo(s2.getId());
        assertThat(out.get(1).getId()).isEqualTo(s1.getId());
    }
}
