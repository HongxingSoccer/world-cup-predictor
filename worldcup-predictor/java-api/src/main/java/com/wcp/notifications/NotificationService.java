package com.wcp.notifications;

import com.wcp.exception.ApiException;
import com.wcp.notifications.dto.NotificationResponse;
import com.wcp.notifications.entity.NotificationEntity;
import com.wcp.security.UserPrincipal;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Notification-centre read/mark-read operations.
 *
 * <p>Notifications are *written* by the Python {@code live_monitor}
 * worker via {@code NotificationDispatcher} — never from Java. This
 * service is read-mostly + the two "mark read" mutations.
 */
@Service
@RequiredArgsConstructor
public class NotificationService {

    private final NotificationRepository repo;

    @Transactional(readOnly = true)
    public Map<String, Object> list(UserPrincipal principal, int limit) {
        requireLogin(principal);
        List<NotificationEntity> rows = repo.findByUserIdOrderByCreatedAtDesc(
                principal.id(), PageRequest.of(0, Math.min(Math.max(1, limit), 200)));
        long unread = repo.countByUserIdAndReadAtIsNull(principal.id());
        return Map.of(
                "items", rows.stream().map(NotificationResponse::from).toList(),
                "unreadCount", unread);
    }

    @Transactional(readOnly = true)
    public long unreadCount(UserPrincipal principal) {
        requireLogin(principal);
        return repo.countByUserIdAndReadAtIsNull(principal.id());
    }

    @Transactional
    public NotificationResponse markRead(UserPrincipal principal, Long id) {
        requireLogin(principal);
        NotificationEntity n = repo.findByIdAndUserId(id, principal.id())
                .orElseThrow(() -> ApiException.notFound("notification " + id));
        if (n.getReadAt() == null) {
            n.setReadAt(OffsetDateTime.now());
        }
        return NotificationResponse.from(n);
    }

    @Transactional
    public int markAllRead(UserPrincipal principal) {
        requireLogin(principal);
        return repo.markAllRead(principal.id(), OffsetDateTime.now());
    }

    private static void requireLogin(UserPrincipal principal) {
        if (principal == null || principal.id() == null) {
            throw ApiException.unauthorized("login required");
        }
    }
}
