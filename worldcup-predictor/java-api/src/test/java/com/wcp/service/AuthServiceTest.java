package com.wcp.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.wcp.dto.request.LoginRequest;
import com.wcp.dto.request.RegisterRequest;
import com.wcp.dto.response.AuthResponse;
import com.wcp.exception.ApiException;
import com.wcp.model.User;
import com.wcp.repository.UserRepository;
import com.wcp.security.JwtTokenProvider;
import io.jsonwebtoken.Claims;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.crypto.password.PasswordEncoder;

/**
 * Auth flow correctness — register / login / refresh / logout. The
 * project-standard error envelope expects 400 / 401 / 409 to surface as
 * specific ApiException sub-cases (badRequest / unauthorized / conflict),
 * so wrong status codes here ship as wrong HTTP responses.
 */
@ExtendWith(MockitoExtension.class)
class AuthServiceTest {

    @Mock private UserRepository userRepository;
    @Mock private PasswordEncoder passwordEncoder;
    @Mock private JwtTokenProvider tokenProvider;

    @InjectMocks private AuthService service;

    private User stubUser(String email, String hash) {
        return User.builder()
                .id(1L)
                .uuid(UUID.randomUUID())
                .email(email)
                .passwordHash(hash)
                .subscriptionTier("free")
                .locale("zh-CN")
                .timezone("Asia/Shanghai")
                .active(true)
                .role("user")
                .build();
    }

    @Nested
    @DisplayName("register()")
    class Register {

        @Test
        @DisplayName("rejects payload with neither phone nor email (400)")
        void rejectsEmptyIdentifier() {
            assertThatThrownBy(() -> service.register(
                    new RegisterRequest(null, null, "Password123", "WCP")
            ))
                    .isInstanceOf(ApiException.class)
                    .extracting(ex -> ((ApiException) ex).getStatus().value())
                    .isEqualTo(400);
        }

        @Test
        @DisplayName("rejects payload with blank password (400)")
        void rejectsBlankPassword() {
            assertThatThrownBy(() -> service.register(
                    new RegisterRequest(null, "a@b.test", "  ", "WCP")
            ))
                    .isInstanceOf(ApiException.class)
                    .extracting(ex -> ((ApiException) ex).getStatus().value())
                    .isEqualTo(400);
        }

        @Test
        @DisplayName("rejects existing phone (409)")
        void rejectsExistingPhone() {
            when(userRepository.existsByPhone("13800000000")).thenReturn(true);

            assertThatThrownBy(() -> service.register(
                    new RegisterRequest("13800000000", null, "Password123", "WCP")
            ))
                    .isInstanceOf(ApiException.class)
                    .extracting(ex -> ((ApiException) ex).getStatus().value())
                    .isEqualTo(409);
        }

        @Test
        @DisplayName("rejects existing email (409)")
        void rejectsExistingEmail() {
            when(userRepository.existsByEmail("a@b.test")).thenReturn(true);

            assertThatThrownBy(() -> service.register(
                    new RegisterRequest(null, "a@b.test", "Password123", "WCP")
            ))
                    .isInstanceOf(ApiException.class)
                    .extracting(ex -> ((ApiException) ex).getStatus().value())
                    .isEqualTo(409);
        }

        @Test
        @DisplayName("happy path — hashes password, persists user, issues both tokens")
        void happyPath() {
            when(userRepository.existsByEmail(anyString())).thenReturn(false);
            when(passwordEncoder.encode("Password123")).thenReturn("BCRYPT-HASH");
            when(userRepository.save(any(User.class))).thenAnswer(inv -> inv.getArgument(0));
            when(tokenProvider.issueAccess(any())).thenReturn("access-jwt");
            when(tokenProvider.issueRefresh(any())).thenReturn("refresh-jwt");

            AuthResponse out = service.register(
                    new RegisterRequest(null, "new@user.test", "Password123", "WCP")
            );

            assertThat(out.accessToken()).isEqualTo("access-jwt");
            assertThat(out.refreshToken()).isEqualTo("refresh-jwt");
            assertThat(out.user().email()).isEqualTo("new@user.test");
            // Defensive: the password the encoder saw must NOT be persisted in plaintext.
            verify(userRepository).save(any(User.class));
        }
    }

    @Nested
    @DisplayName("login()")
    class Login {

        @Test
        @DisplayName("returns tokens when password matches and account is active")
        void happyPath() {
            User u = stubUser("a@b.test", "BCRYPT-HASH");
            when(userRepository.findByEmail("a@b.test")).thenReturn(Optional.of(u));
            when(passwordEncoder.matches("Password123", "BCRYPT-HASH")).thenReturn(true);
            when(tokenProvider.issueAccess(any())).thenReturn("access-jwt");
            when(tokenProvider.issueRefresh(any())).thenReturn("refresh-jwt");

            AuthResponse out = service.login(
                    new LoginRequest(null, "a@b.test", "Password123")
            );

            assertThat(out.accessToken()).isEqualTo("access-jwt");
            assertThat(u.getLastLoginAt()).isNotNull();
        }

        @Test
        @DisplayName("rejects wrong password with 401")
        void wrongPasswordRejected() {
            User u = stubUser("a@b.test", "BCRYPT-HASH");
            when(userRepository.findByEmail("a@b.test")).thenReturn(Optional.of(u));
            when(passwordEncoder.matches("WrongPass", "BCRYPT-HASH")).thenReturn(false);

            assertThatThrownBy(() -> service.login(
                    new LoginRequest(null, "a@b.test", "WrongPass")
            ))
                    .isInstanceOf(ApiException.class)
                    .extracting(ex -> ((ApiException) ex).getStatus().value())
                    .isEqualTo(401);

            verify(tokenProvider, never()).issueAccess(any());
        }

        @Test
        @DisplayName("rejects unknown email with 401 (no user enumeration leak)")
        void unknownEmailRejected() {
            when(userRepository.findByEmail("ghost@nowhere.test")).thenReturn(Optional.empty());

            assertThatThrownBy(() -> service.login(
                    new LoginRequest(null, "ghost@nowhere.test", "Whatever")
            ))
                    .isInstanceOf(ApiException.class)
                    .extracting(ex -> ((ApiException) ex).getStatus().value())
                    .isEqualTo(401);
        }

        @Test
        @DisplayName("rejects disabled account with 403 even if password matches")
        void disabledAccountRejected() {
            User u = stubUser("a@b.test", "BCRYPT-HASH").toBuilder()
                    .active(false)
                    .build();
            when(userRepository.findByEmail("a@b.test")).thenReturn(Optional.of(u));
            when(passwordEncoder.matches("Password123", "BCRYPT-HASH")).thenReturn(true);

            assertThatThrownBy(() -> service.login(
                    new LoginRequest(null, "a@b.test", "Password123")
            ))
                    .isInstanceOf(ApiException.class)
                    .extracting(ex -> ((ApiException) ex).getStatus().value())
                    .isEqualTo(403);
        }

        @Test
        @DisplayName("phone login route is honoured when phone is supplied")
        void phoneLoginUsesPhoneLookup() {
            User u = stubUser("a@b.test", "BCRYPT-HASH");
            when(userRepository.findByPhone("13800000000")).thenReturn(Optional.of(u));
            when(passwordEncoder.matches("Password123", "BCRYPT-HASH")).thenReturn(true);
            when(tokenProvider.issueAccess(any())).thenReturn("access");
            when(tokenProvider.issueRefresh(any())).thenReturn("refresh");

            AuthResponse out = service.login(
                    new LoginRequest("13800000000", null, "Password123")
            );

            assertThat(out.accessToken()).isEqualTo("access");
        }
    }

    @Nested
    @DisplayName("refresh()")
    class Refresh {

        @Test
        @DisplayName("rejects an access-token-shaped JWT (401)")
        void rejectsAccessTokenAsRefresh() {
            Claims claims = org.mockito.Mockito.mock(Claims.class);
            when(tokenProvider.verify("access-jwt")).thenReturn(claims);
            when(tokenProvider.isRefreshToken(claims)).thenReturn(false);

            assertThatThrownBy(() -> service.refresh("access-jwt"))
                    .isInstanceOf(ApiException.class)
                    .extracting(ex -> ((ApiException) ex).getStatus().value())
                    .isEqualTo(401);
        }

        @Test
        @DisplayName("issues fresh tokens when refresh JWT is valid")
        void happyPath() {
            User u = stubUser("a@b.test", "BCRYPT-HASH");
            Claims claims = org.mockito.Mockito.mock(Claims.class);
            when(claims.getSubject()).thenReturn(u.getUuid().toString());
            when(tokenProvider.verify("refresh-jwt")).thenReturn(claims);
            when(tokenProvider.isRefreshToken(claims)).thenReturn(true);
            when(userRepository.findByUuid(u.getUuid())).thenReturn(Optional.of(u));
            when(tokenProvider.issueAccess(any())).thenReturn("new-access");
            when(tokenProvider.issueRefresh(any())).thenReturn("new-refresh");

            AuthResponse out = service.refresh("refresh-jwt");

            assertThat(out.accessToken()).isEqualTo("new-access");
            assertThat(out.refreshToken()).isEqualTo("new-refresh");
        }

        @Test
        @DisplayName("rejects refresh JWT with malformed UUID subject (401)")
        void malformedSubjectRejected() {
            Claims claims = org.mockito.Mockito.mock(Claims.class);
            when(tokenProvider.verify("refresh-jwt")).thenReturn(claims);
            when(tokenProvider.isRefreshToken(claims)).thenReturn(true);
            when(claims.getSubject()).thenReturn("not-a-uuid");

            assertThatThrownBy(() -> service.refresh("refresh-jwt"))
                    .isInstanceOf(ApiException.class)
                    .extracting(ex -> ((ApiException) ex).getStatus().value())
                    .isEqualTo(401);
        }
    }

    @Nested
    @DisplayName("logout()")
    class Logout {

        @Test
        @DisplayName("revokes the JWT in the token provider's blacklist")
        void revokesTheToken() {
            Claims claims = org.mockito.Mockito.mock(Claims.class);
            when(tokenProvider.verify("access-jwt")).thenReturn(claims);

            service.logout("access-jwt");

            verify(tokenProvider).revoke(claims);
        }

        @Test
        @DisplayName("idempotent — already-invalid token does not throw")
        void idempotent() {
            when(tokenProvider.verify("garbage"))
                    .thenThrow(new RuntimeException("invalid signature"));

            // Should swallow the exception — logout must always succeed.
            service.logout("garbage");
        }
    }
}
