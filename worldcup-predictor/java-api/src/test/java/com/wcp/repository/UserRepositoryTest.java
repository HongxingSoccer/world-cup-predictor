package com.wcp.repository;

import static org.assertj.core.api.Assertions.assertThat;

import com.wcp.model.User;
import java.util.UUID;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase.Replace;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.test.context.ActiveProfiles;

@DataJpaTest
@AutoConfigureTestDatabase(replace = Replace.NONE)
@ActiveProfiles("test")
class UserRepositoryTest {

    @Autowired private UserRepository users;

    private static User newUser(String email, String phone) {
        return User.builder()
                .uuid(UUID.randomUUID())
                .email(email)
                .phone(phone)
                .passwordHash("BCRYPT-HASH")
                .nickname("nick")
                .subscriptionTier("free")
                .locale("zh-CN")
                .timezone("Asia/Shanghai")
                .active(true)
                .role("user")
                .build();
    }

    @Test
    @DisplayName("round-trips by email")
    void findByEmail() {
        users.save(newUser("a@b.test", null));

        assertThat(users.findByEmail("a@b.test"))
                .isPresent()
                .hasValueSatisfying(u -> assertThat(u.getEmail()).isEqualTo("a@b.test"));
        assertThat(users.findByEmail("ghost@nowhere.test")).isEmpty();
    }

    @Test
    @DisplayName("round-trips by phone")
    void findByPhone() {
        users.save(newUser(null, "13800000000"));

        assertThat(users.findByPhone("13800000000")).isPresent();
        assertThat(users.findByPhone("13900000000")).isEmpty();
    }

    @Test
    @DisplayName("round-trips by uuid (the JWT subject)")
    void findByUuid() {
        UUID uuid = UUID.randomUUID();
        User saved = users.save(User.builder()
                .uuid(uuid)
                .email("x@y.test")
                .passwordHash("h")
                .subscriptionTier("free")
                .locale("zh-CN").timezone("Asia/Shanghai")
                .active(true).role("user").build());

        assertThat(users.findByUuid(uuid))
                .isPresent()
                .hasValueSatisfying(u -> assertThat(u.getId()).isEqualTo(saved.getId()));
        assertThat(users.findByUuid(UUID.randomUUID())).isEmpty();
    }

    @Test
    @DisplayName("existsByEmail / existsByPhone power the registration uniqueness check")
    void existsCheck() {
        users.save(newUser("dup@b.test", "13700000000"));

        assertThat(users.existsByEmail("dup@b.test")).isTrue();
        assertThat(users.existsByEmail("free@b.test")).isFalse();
        assertThat(users.existsByPhone("13700000000")).isTrue();
        assertThat(users.existsByPhone("13800000000")).isFalse();
    }
}
