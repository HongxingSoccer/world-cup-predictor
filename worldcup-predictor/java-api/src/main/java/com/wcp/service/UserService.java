package com.wcp.service;

import com.wcp.exception.ApiException;
import com.wcp.model.User;
import com.wcp.repository.UserRepository;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

/** Read / update operations on the local user record. */
@Service
@RequiredArgsConstructor
public class UserService {

    private final UserRepository userRepository;

    public User loadByUuid(UUID uuid) {
        return userRepository.findByUuid(uuid)
                .orElseThrow(() -> ApiException.notFound("user"));
    }

    public User updateProfile(UUID uuid, String nickname, String avatarUrl,
                              String locale, String timezone) {
        User user = loadByUuid(uuid);
        if (nickname != null) user.setNickname(nickname);
        if (avatarUrl != null) user.setAvatarUrl(avatarUrl);
        if (locale != null) user.setLocale(locale);
        if (timezone != null) user.setTimezone(timezone);
        return userRepository.save(user);
    }
}
