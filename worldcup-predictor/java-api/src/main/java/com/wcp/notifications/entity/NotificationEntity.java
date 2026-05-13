package com.wcp.notifications.entity;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.OffsetDateTime;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

/**
 * Maps to {@code push_notifications} (extended by Alembic 0007).
 *
 * <p>The Python side persists the canonical row when it fires a
 * notification; this entity reads it back for the notification-centre
 * endpoints. Writes from Java are limited to status-change ops
 * (mark-read, mark-all-read).
 */
@Entity
@Table(name = "push_notifications")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder(toBuilder = true)
public class NotificationEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false)
    private Long userId;

    @Column(nullable = false, length = 20)
    private String channel;

    /** Maps to the Python {@code NotificationKind} enum strings. */
    @Column(name = "notification_type", nullable = false, length = 30)
    private String kind;

    @Column(nullable = false, length = 200)
    private String title;

    @Column(nullable = false, columnDefinition = "text")
    private String body;

    @Column(name = "target_url", columnDefinition = "text")
    private String targetUrl;

    @Column(nullable = false, length = 20)
    private String status;

    @Column(name = "position_id")
    private Long positionId;

    @Column(name = "match_id")
    private Long matchId;

    /** Payload JSON. Read as raw String; the controller passes through. */
    @Column(columnDefinition = "jsonb")
    @JdbcTypeCode(SqlTypes.JSON)
    private JsonNode meta;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    @Setter
    @Column(name = "read_at")
    private OffsetDateTime readAt;
}
