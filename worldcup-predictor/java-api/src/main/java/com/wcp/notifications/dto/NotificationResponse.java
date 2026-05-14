package com.wcp.notifications.dto;

import com.fasterxml.jackson.databind.JsonNode;
import com.wcp.notifications.entity.NotificationEntity;
import java.time.OffsetDateTime;

public record NotificationResponse(
        Long id,
        String kind,
        String title,
        String body,
        Long positionId,
        Long matchId,
        String targetUrl,
        JsonNode payload,
        OffsetDateTime createdAt,
        OffsetDateTime readAt
) {
    public static NotificationResponse from(NotificationEntity e) {
        return new NotificationResponse(
                e.getId(),
                e.getKind(),
                e.getTitle(),
                e.getBody(),
                e.getPositionId(),
                e.getMatchId(),
                e.getTargetUrl(),
                e.getMeta(),
                e.getCreatedAt(),
                e.getReadAt());
    }
}
