package com.wcp.repository;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.wcp.model.UserFavorite;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase.Replace;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.test.context.ActiveProfiles;

@DataJpaTest
@AutoConfigureTestDatabase(replace = Replace.NONE)
@ActiveProfiles("test")
class UserFavoriteRepositoryTest {

    @Autowired private UserFavoriteRepository favorites;

    private static UserFavorite fav(long userId, long matchId, Instant when) {
        return UserFavorite.builder()
                .userId(userId)
                .matchId(matchId)
                .createdAt(when)
                .build();
    }

    @Test
    @DisplayName("findByUserIdAndMatchId hits the compound index")
    void compoundLookup() {
        favorites.save(fav(1L, 100L, Instant.now()));
        favorites.save(fav(1L, 101L, Instant.now()));

        assertThat(favorites.findByUserIdAndMatchId(1L, 100L)).isPresent();
        assertThat(favorites.findByUserIdAndMatchId(1L, 999L)).isEmpty();
        // Defensive: another user's favourite must NOT match.
        assertThat(favorites.findByUserIdAndMatchId(2L, 100L)).isEmpty();
    }

    @Test
    @DisplayName("uq_user_favorites_user_match prevents duplicate (user, match) entries")
    void uniqueConstraintHonoured() {
        favorites.save(fav(1L, 100L, Instant.now()));
        favorites.flush();

        // Inserting the same (userId, matchId) pair must blow up — the
        // service-layer toggleFavorite relies on the row being absent OR
        // present, never duplicated.
        assertThatThrownBy(() -> {
            favorites.save(fav(1L, 100L, Instant.now()));
            favorites.flush();
        }).isInstanceOf(DataIntegrityViolationException.class);
    }

    @Test
    @DisplayName("findByUserIdOrderByCreatedAtDesc returns newest favorites first")
    void newestFirst() throws InterruptedException {
        // The createdAt the builder sets is overwritten by Hibernate's
        // @CreationTimestamp at flush time, so ordering is determined by
        // the *save* order. Tiny sleeps guarantee distinct timestamps even
        // on hosts with low clock granularity.
        favorites.saveAndFlush(fav(1L, 100L, Instant.now()));
        Thread.sleep(5);
        favorites.saveAndFlush(fav(1L, 102L, Instant.now()));
        Thread.sleep(5);
        favorites.saveAndFlush(fav(1L, 101L, Instant.now()));

        List<UserFavorite> out = favorites.findByUserIdOrderByCreatedAtDesc(1L);

        // Last-saved must come first (DESC). The matchId values are
        // intentionally non-monotonic so a "ORDER BY id DESC" regression
        // would still surface.
        assertThat(out).extracting(UserFavorite::getMatchId)
                .containsExactly(101L, 102L, 100L);
    }
}
