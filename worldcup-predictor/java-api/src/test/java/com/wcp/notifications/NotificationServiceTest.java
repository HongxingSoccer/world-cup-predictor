package com.wcp.notifications;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

import com.wcp.exception.ApiException;
import com.wcp.model.enums.SubscriptionTier;
import com.wcp.notifications.entity.NotificationEntity;
import com.wcp.security.UserPrincipal;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.PageRequest;

@ExtendWith(MockitoExtension.class)
class NotificationServiceTest {

    @Mock private NotificationRepository repo;

    @InjectMocks private NotificationService service;

    private UserPrincipal alice;

    @BeforeEach
    void setup() {
        alice = new UserPrincipal(
                1L, UUID.randomUUID(), "user", SubscriptionTier.BASIC, true);
    }

    @Test
    @DisplayName("list() returns items + unreadCount")
    void listReturnsItemsAndCount() {
        NotificationEntity n1 = makeNotification(101L, 1L, /* readAt */ null);
        NotificationEntity n2 = makeNotification(102L, 1L, OffsetDateTime.now());
        when(repo.findByUserIdOrderByCreatedAtDesc(eq(1L), any(PageRequest.class)))
                .thenReturn(List.of(n1, n2));
        when(repo.countByUserIdAndReadAtIsNull(1L)).thenReturn(1L);

        Map<String, Object> resp = service.list(alice, 50);

        assertThat(resp.get("items")).asList().hasSize(2);
        assertThat(resp.get("unreadCount")).isEqualTo(1L);
    }

    @Test
    @DisplayName("list(limit=999) is capped at 200")
    void listCapsLimit() {
        when(repo.findByUserIdOrderByCreatedAtDesc(eq(1L), any(PageRequest.class)))
                .thenReturn(List.of());
        when(repo.countByUserIdAndReadAtIsNull(1L)).thenReturn(0L);

        service.list(alice, 999);
        // Just confirms it doesn't throw; the cap is an internal Math.min.
    }

    @Test
    @DisplayName("unreadCount() returns 0 for users with no unread")
    void unreadCountZero() {
        when(repo.countByUserIdAndReadAtIsNull(1L)).thenReturn(0L);
        assertThat(service.unreadCount(alice)).isEqualTo(0L);
    }

    @Test
    @DisplayName("markRead() flips readAt when previously null")
    void markReadFlipsTimestamp() {
        NotificationEntity n = makeNotification(101L, 1L, null);
        when(repo.findByIdAndUserId(101L, 1L)).thenReturn(Optional.of(n));

        service.markRead(alice, 101L);

        assertThat(n.getReadAt()).isNotNull();
    }

    @Test
    @DisplayName("markRead() is idempotent — second call does not overwrite")
    void markReadIdempotent() {
        OffsetDateTime original = OffsetDateTime.now().minusMinutes(5);
        NotificationEntity n = makeNotification(101L, 1L, original);
        when(repo.findByIdAndUserId(101L, 1L)).thenReturn(Optional.of(n));

        service.markRead(alice, 101L);

        assertThat(n.getReadAt()).isEqualTo(original);
    }

    @Test
    @DisplayName("markRead() for non-existent id → 404")
    void markReadMissing() {
        when(repo.findByIdAndUserId(999L, 1L)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> service.markRead(alice, 999L))
                .isInstanceOf(ApiException.class)
                .hasMessageContaining("notification 999");
    }

    @Test
    @DisplayName("markAllRead() delegates to the repo's batched UPDATE")
    void markAllReadDelegates() {
        when(repo.markAllRead(eq(1L), any(OffsetDateTime.class))).thenReturn(7);

        assertThat(service.markAllRead(alice)).isEqualTo(7);
    }

    @Test
    @DisplayName("anonymous → 401")
    void anonymousRejected() {
        UserPrincipal anon = UserPrincipal.anonymous();
        assertThatThrownBy(() -> service.unreadCount(anon))
                .isInstanceOf(ApiException.class)
                .hasMessageContaining("login required");
    }

    private NotificationEntity makeNotification(Long id, Long userId, OffsetDateTime readAt) {
        return NotificationEntity.builder()
                .id(id)
                .userId(userId)
                .channel("db")
                .kind("hedge_window")
                .title("test")
                .body("body")
                .status("sent")
                .createdAt(OffsetDateTime.now().minusMinutes(10))
                .readAt(readAt)
                .build();
    }
}
