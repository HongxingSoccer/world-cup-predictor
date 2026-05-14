package com.wcp.positions;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;

import com.wcp.exception.ApiException;
import com.wcp.model.enums.SubscriptionTier;
import com.wcp.positions.dto.CreatePositionRequest;
import com.wcp.positions.dto.PositionResponse;
import com.wcp.positions.dto.UpdateStatusRequest;
import com.wcp.positions.entity.PositionEntity;
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
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class PositionServiceTest {

    @Mock private PositionRepository repo;

    @InjectMocks private PositionService service;

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
    @DisplayName("create() inserts a row for the caller")
    void createInserts() {
        CreatePositionRequest req = new CreatePositionRequest(
                123L, "pinnacle", "1x2", "home",
                new BigDecimal("100"), new BigDecimal("2.10"),
                OffsetDateTime.now(), null);
        when(repo.save(any(PositionEntity.class)))
                .thenAnswer(invocation -> {
                    PositionEntity e = invocation.getArgument(0);
                    return e.toBuilder().id(42L).build();
                });

        PositionResponse resp = service.create(alice, req);

        assertThat(resp.id()).isEqualTo(42L);
        assertThat(resp.userId()).isEqualTo(1L);
        assertThat(resp.platform()).isEqualTo("pinnacle");
        assertThat(resp.market()).isEqualTo("1x2");
    }

    @Test
    @DisplayName("create() rejects unsupported markets")
    void createRejectsUnknownMarket() {
        CreatePositionRequest req = new CreatePositionRequest(
                123L, "pinnacle", "esoteric_market", "home",
                new BigDecimal("100"), new BigDecimal("2.10"),
                OffsetDateTime.now(), null);

        assertThatThrownBy(() -> service.create(alice, req))
                .isInstanceOf(ApiException.class)
                .hasMessageContaining("unsupported market");
    }

    @Test
    @DisplayName("list() with no filter delegates to the unfiltered repo query")
    void listAllUnfiltered() {
        when(repo.findByUserIdOrderByCreatedAtDesc(1L)).thenReturn(List.of(makeEntity(11L, 1L)));

        List<PositionResponse> rows = service.list(alice, null);

        assertThat(rows).hasSize(1);
        assertThat(rows.get(0).id()).isEqualTo(11L);
    }

    @Test
    @DisplayName("list(status=active) filters")
    void listWithStatusFilter() {
        when(repo.findByUserIdAndStatusOrderByCreatedAtDesc(1L, "active"))
                .thenReturn(List.of(makeEntity(12L, 1L)));

        List<PositionResponse> rows = service.list(alice, "active");

        assertThat(rows).hasSize(1);
    }

    @Test
    @DisplayName("get() for another user's position → 404 (no existence leak)")
    void getCrossUserReturns404() {
        when(repo.findByIdAndUserId(99L, bob.id())).thenReturn(Optional.empty());

        assertThatThrownBy(() -> service.get(bob, 99L))
                .isInstanceOf(ApiException.class)
                .hasMessageContaining("not found");
    }

    @Test
    @DisplayName("updateStatus() validates the requested value")
    void updateStatusValidates() {
        UpdateStatusRequest req = new UpdateStatusRequest("banana");
        assertThatThrownBy(() -> service.updateStatus(alice, 1L, req))
                .isInstanceOf(ApiException.class)
                .hasMessageContaining("unsupported status");
    }

    @Test
    @DisplayName("updateStatus(active → hedged) mutates the entity")
    void updateStatusFlipsToHedged() {
        PositionEntity e = makeEntity(33L, 1L);
        when(repo.findByIdAndUserId(33L, 1L)).thenReturn(Optional.of(e));

        PositionResponse resp = service.updateStatus(
                alice, 33L, new UpdateStatusRequest("hedged"));

        assertThat(resp.status()).isEqualTo("hedged");
    }

    @Test
    @DisplayName("softDelete() sets status to 'cancelled'")
    void softDeleteSetsCancelled() {
        PositionEntity e = makeEntity(44L, 1L);
        when(repo.findByIdAndUserId(44L, 1L)).thenReturn(Optional.of(e));

        PositionResponse resp = service.softDelete(alice, 44L);

        assertThat(resp.status()).isEqualTo("cancelled");
    }

    @Test
    @DisplayName("anonymous caller is rejected with 401")
    void anonymousRejected() {
        UserPrincipal anon = UserPrincipal.anonymous();
        assertThatThrownBy(() -> service.list(anon, null))
                .isInstanceOf(ApiException.class)
                .hasMessageContaining("login required");
    }

    private PositionEntity makeEntity(Long id, Long userId) {
        return PositionEntity.builder()
                .id(id)
                .userId(userId)
                .matchId(123L)
                .platform("pinnacle")
                .market("1x2")
                .outcome("home")
                .stake(new BigDecimal("100"))
                .odds(new BigDecimal("2.10"))
                .placedAt(OffsetDateTime.now())
                .status("active")
                .createdAt(OffsetDateTime.now())
                .updatedAt(OffsetDateTime.now())
                .build();
    }
}
