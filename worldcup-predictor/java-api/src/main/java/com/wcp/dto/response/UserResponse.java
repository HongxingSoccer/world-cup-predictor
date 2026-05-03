package com.wcp.dto.response;

import com.wcp.model.User;
import java.time.Instant;
import java.util.UUID;

/** User profile shape returned by /users/me + embedded in /auth responses. */
public record UserResponse(
        UUID uuid,
        String phone,
        String email,
        String nickname,
        String avatarUrl,
        String subscriptionTier,
        Instant subscriptionExpires,
        String locale,
        String timezone,
        String role
) {

    public static UserResponse from(User user) {
        return new UserResponse(
                user.getUuid(),
                user.getPhone(),
                user.getEmail(),
                user.getNickname(),
                user.getAvatarUrl(),
                user.getSubscriptionTier(),
                user.getSubscriptionExpires(),
                user.getLocale(),
                user.getTimezone(),
                user.getRole()
        );
    }
}
