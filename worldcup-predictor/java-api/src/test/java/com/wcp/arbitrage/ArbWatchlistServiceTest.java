package com.wcp.arbitrage;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.wcp.arbitrage.dto.CreateWatchlistRequest;
import com.wcp.arbitrage.dto.WatchlistResponse;
import com.wcp.arbitrage.entity.ArbWatchlistEntity;
import com.wcp.exception.ApiException;
import com.wcp.model.enums.SubscriptionTier;
import com.wcp.security.UserPrincipal;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.Spy;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class ArbWatchlistServiceTest {

    @Mock private ArbWatchlistRepository repo;
    @Spy private ObjectMapper objectMapper = new ObjectMapper();

    @InjectMocks private ArbWatchlistService service;

    private UserPrincipal alice;
    private UserPrincipal bob;

    @BeforeEach
    void setup() {
        alice = new UserPrincipal(
                1L, UUID.randomUUID(), "user", SubscriptionTier.BASIC, true);
        bob = new UserPrincipal(
                2L, UUID.randomUUID(), "user", SubscriptionTier.BASIC, true);
    }

    @Test
    @DisplayName("create() persists a rule scoped to the caller with defaults filled in")
    void createUsesCallerAndDefaults() {
        CreateWatchlistRequest req = new CreateWatchlistRequest(
                null, List.of("1x2"), null, null);
        when(repo.save(any(ArbWatchlistEntity.class)))
                .thenAnswer(invocation -> {
                    ArbWatchlistEntity e = invocation.getArgument(0);
                    return e.toBuilder().id(99L).createdAt(OffsetDateTime.now()).build();
                });

        WatchlistResponse resp = service.create(alice, req);

        assertThat(resp.id()).isEqualTo(99L);
        assertThat(resp.userId()).isEqualTo(1L);
        assertThat(resp.minProfitMargin()).isEqualByComparingTo("0.01"); // default
        assertThat(resp.notifyEnabled()).isTrue(); // default
    }

    @Test
    @DisplayName("create() round-trips an explicit margin + notify flag")
    void createUsesProvidedValues() {
        CreateWatchlistRequest req = new CreateWatchlistRequest(
                42L, null, new BigDecimal("0.05"), false);
        when(repo.save(any(ArbWatchlistEntity.class)))
                .thenAnswer(invocation -> {
                    ArbWatchlistEntity e = invocation.getArgument(0);
                    return e.toBuilder().id(100L).createdAt(OffsetDateTime.now()).build();
                });

        WatchlistResponse resp = service.create(alice, req);

        assertThat(resp.competitionId()).isEqualTo(42L);
        assertThat(resp.minProfitMargin()).isEqualByComparingTo("0.05");
        assertThat(resp.notifyEnabled()).isFalse();
    }

    @Test
    @DisplayName("list() is scoped to the caller")
    void listScopedToCaller() {
        when(repo.findByUserIdOrderByCreatedAtDesc(1L))
                .thenReturn(List.of(makeRule(11L, 1L)));

        List<WatchlistResponse> rows = service.list(alice);

        assertThat(rows).hasSize(1);
        assertThat(rows.get(0).userId()).isEqualTo(1L);
    }

    @Test
    @DisplayName("delete() for another user's rule → 404")
    void deleteCrossUserReturns404() {
        when(repo.findByIdAndUserId(99L, bob.id())).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.delete(bob, 99L))
                .isInstanceOf(ApiException.class)
                .hasMessageContaining("not found");
    }

    @Test
    @DisplayName("delete() removes the row")
    void deleteRemoves() {
        ArbWatchlistEntity row = makeRule(33L, 1L);
        when(repo.findByIdAndUserId(33L, 1L)).thenReturn(Optional.of(row));

        service.delete(alice, 33L);

        verify(repo).delete(row);
    }

    @Test
    @DisplayName("anonymous caller is rejected")
    void anonymousRejected() {
        UserPrincipal anon = UserPrincipal.anonymous();
        assertThatThrownBy(() -> service.list(anon))
                .isInstanceOf(ApiException.class)
                .hasMessageContaining("login required");
    }

    private ArbWatchlistEntity makeRule(Long id, Long userId) {
        return ArbWatchlistEntity.builder()
                .id(id)
                .userId(userId)
                .minProfitMargin(new BigDecimal("0.02"))
                .notifyEnabled(true)
                .createdAt(OffsetDateTime.now())
                .build();
    }
}
