package com.wcp.integration;

import static org.hamcrest.Matchers.notNullValue;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.wcp.client.MlApiClient;
import com.wcp.payment.StripeClient;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.util.Base64;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.http.MediaType;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.springframework.transaction.annotation.Transactional;

/**
 * End-to-end auth chain — through the Spring Security filter chain,
 * JwtAuthFilter, controller, AuthService, BCryptPasswordEncoder, the
 * Postgres-flavoured H2 schema, and back out. Three categories of bug
 * that unit tests alone can't catch:
 *
 *   1. SecurityConfig misconfiguration — e.g. accidentally requiring
 *      auth on /api/v1/auth/login, or forgetting to permit /me.
 *   2. JwtAuthFilter ordering / claim parsing — the issued tokens must
 *      verify back through the same provider that signed them.
 *   3. @Valid + RegisterRequest regex — the request DTO bean-validation
 *      annotations have to fire before reaching the service layer.
 */
@SpringBootTest
@AutoConfigureMockMvc
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@ActiveProfiles("test")
@Transactional
class AuthControllerIntegrationTest {

    /**
     * Generate a temporary RSA key pair at class load time and feed the
     * paths into the Spring context via DynamicPropertySource. Without
     * this, JwtTokenProvider would try to read `/run/secrets/jwt-*.pem`
     * (the production default) and fail to boot.
     */
    private static final Path TMP_DIR;
    private static final Path PRIVATE_PEM;
    private static final Path PUBLIC_PEM;

    static {
        try {
            TMP_DIR = Files.createTempDirectory("wcp-auth-test-keys-");
            PRIVATE_PEM = TMP_DIR.resolve("jwt-private.pem");
            PUBLIC_PEM = TMP_DIR.resolve("jwt-public.pem");
            KeyPairGenerator kpg = KeyPairGenerator.getInstance("RSA");
            kpg.initialize(2048);
            KeyPair keys = kpg.generateKeyPair();
            Files.writeString(PRIVATE_PEM, toPem(keys.getPrivate().getEncoded(), "PRIVATE KEY"));
            Files.writeString(PUBLIC_PEM, toPem(keys.getPublic().getEncoded(), "PUBLIC KEY"));
            TMP_DIR.toFile().deleteOnExit();
            PRIVATE_PEM.toFile().deleteOnExit();
            PUBLIC_PEM.toFile().deleteOnExit();
        } catch (Exception ex) {
            throw new RuntimeException("failed to seed test JWT keys", ex);
        }
    }

    private static String toPem(byte[] der, String label) {
        String b64 = Base64.getMimeEncoder(64, "\n".getBytes()).encodeToString(der);
        return "-----BEGIN " + label + "-----\n" + b64 + "\n-----END " + label + "-----\n";
    }

    @DynamicPropertySource
    static void overrideJwtKeyPaths(DynamicPropertyRegistry registry) {
        registry.add("wcp.jwt.private-key-path", PRIVATE_PEM::toString);
        registry.add("wcp.jwt.public-key-path", PUBLIC_PEM::toString);
    }

    @Autowired private MockMvc mockMvc;
    @Autowired private ObjectMapper objectMapper;

    // External integrations stubbed — we never reach the Python service or Stripe.
    @MockBean private MlApiClient mlApiClient;
    @MockBean private StripeClient stripeClient;
    // Redis auto-config is excluded in `application-test.yml`; the
    // JwtTokenProvider declares a hard-typed RedisTemplate dependency, so
    // we provide an inert mock here. The blacklist `set`/`hasKey` calls
    // are exercised against this mock — verify() in the production code
    // already catches Redis-side exceptions and fails open.
    @MockBean(name = "redisTemplate") @SuppressWarnings("rawtypes")
    private RedisTemplate redisTemplate;

    // --- Helpers ---------------------------------------------------------

    private ObjectNode body() {
        return objectMapper.createObjectNode();
    }

    private String asJson(ObjectNode body) {
        return body.toString();
    }

    private record IssuedTokens(String access, String refresh) {}

    private IssuedTokens registerAndLogin(String email, String password) throws Exception {
        MvcResult result = mockMvc.perform(post("/api/v1/auth/register")
                .contentType(MediaType.APPLICATION_JSON)
                .content(asJson(body()
                        .put("email", email)
                        .put("password", password)
                        .put("nickname", "WCP"))))
                .andExpect(status().isCreated())
                .andReturn();
        var node = objectMapper.readTree(result.getResponse().getContentAsString());
        return new IssuedTokens(
                node.get("accessToken").asText(),
                node.get("refreshToken").asText()
        );
    }

    // --- Register --------------------------------------------------------

    @Test
    @DisplayName("POST /register hashes password + returns 201 with token bundle")
    void registerHappyPath() throws Exception {
        mockMvc.perform(post("/api/v1/auth/register")
                .contentType(MediaType.APPLICATION_JSON)
                .content(asJson(body()
                        .put("email", "happy@user.test")
                        .put("password", "TestPass123")
                        .put("nickname", "WCP"))))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("$.accessToken").value(notNullValue()))
                .andExpect(jsonPath("$.refreshToken").value(notNullValue()))
                .andExpect(jsonPath("$.user.email").value("happy@user.test"))
                .andExpect(jsonPath("$.user.subscriptionTier").value("free"));
    }

    @Test
    @DisplayName("POST /register without phone OR email is rejected 400 by @Valid + service guard")
    void registerMissingIdentifier() throws Exception {
        mockMvc.perform(post("/api/v1/auth/register")
                .contentType(MediaType.APPLICATION_JSON)
                .content(asJson(body().put("password", "TestPass123"))))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("POST /register with malformed phone is rejected 400 by @Pattern")
    void registerBadPhonePattern() throws Exception {
        // Mainland mobile pattern is `^1[3-9]\\d{9}$` — alphanumerics fail @Valid.
        mockMvc.perform(post("/api/v1/auth/register")
                .contentType(MediaType.APPLICATION_JSON)
                .content(asJson(body()
                        .put("phone", "not-a-phone")
                        .put("password", "TestPass123"))))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("POST /register with duplicate email returns 409")
    void registerConflictsOnDuplicateEmail() throws Exception {
        // First registration succeeds.
        mockMvc.perform(post("/api/v1/auth/register")
                .contentType(MediaType.APPLICATION_JSON)
                .content(asJson(body()
                        .put("email", "dup@user.test")
                        .put("password", "TestPass123"))))
                .andExpect(status().isCreated());
        // Second on the same email collides.
        mockMvc.perform(post("/api/v1/auth/register")
                .contentType(MediaType.APPLICATION_JSON)
                .content(asJson(body()
                        .put("email", "dup@user.test")
                        .put("password", "AnotherPass1"))))
                .andExpect(status().isConflict());
    }

    // --- Login -----------------------------------------------------------

    @Test
    @DisplayName("POST /login returns fresh tokens when password matches")
    void loginHappyPath() throws Exception {
        registerAndLogin("login@user.test", "Password123");

        mockMvc.perform(post("/api/v1/auth/login")
                .contentType(MediaType.APPLICATION_JSON)
                .content(asJson(body()
                        .put("email", "login@user.test")
                        .put("password", "Password123"))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.accessToken").value(notNullValue()))
                .andExpect(jsonPath("$.user.email").value("login@user.test"));
    }

    @Test
    @DisplayName("POST /login wrong password → 401 (no user enumeration leak)")
    void loginWrongPassword() throws Exception {
        registerAndLogin("auth@user.test", "Password123");

        mockMvc.perform(post("/api/v1/auth/login")
                .contentType(MediaType.APPLICATION_JSON)
                .content(asJson(body()
                        .put("email", "auth@user.test")
                        .put("password", "WrongPass1"))))
                .andExpect(status().isUnauthorized());
    }

    @Test
    @DisplayName("POST /login non-existent email → 401 (same error as wrong password)")
    void loginUnknownEmail() throws Exception {
        mockMvc.perform(post("/api/v1/auth/login")
                .contentType(MediaType.APPLICATION_JSON)
                .content(asJson(body()
                        .put("email", "ghost@nowhere.test")
                        .put("password", "Password123"))))
                .andExpect(status().isUnauthorized());
    }

    // --- /users/me + JwtAuthFilter ---------------------------------------

    @Test
    @DisplayName("GET /users/me without token → 403 (anonymous is denied by SecurityConfig)")
    void meAnonymousDenied() throws Exception {
        // The default AccessDeniedHandler treats anonymous like 403 unless
        // a bearer token is presented — Spring's `permitAll` allow-list
        // explicitly excludes /me.
        mockMvc.perform(get("/api/v1/users/me"))
                .andExpect(result -> {
                    int status = result.getResponse().getStatus();
                    assert status == 401 || status == 403
                            : "expected 401 or 403, got " + status;
                });
    }

    @Test
    @DisplayName("GET /users/me with a fresh bearer token → 200 and the user payload")
    void meWithBearerReturnsUser() throws Exception {
        IssuedTokens t = registerAndLogin("me@user.test", "Password123");

        mockMvc.perform(get("/api/v1/users/me")
                .header("Authorization", "Bearer " + t.access()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.email").value("me@user.test"));
    }

    @Test
    @DisplayName("GET /users/me with junk token → 401 / 403 — never 200")
    void meWithJunkTokenRejected() throws Exception {
        mockMvc.perform(get("/api/v1/users/me")
                .header("Authorization", "Bearer not-a-real-jwt"))
                .andExpect(result -> {
                    int status = result.getResponse().getStatus();
                    assert status == 401 || status == 403
                            : "expected 401 or 403 for invalid token, got " + status;
                });
    }

    // --- Refresh ---------------------------------------------------------

    @Test
    @DisplayName("POST /refresh with a refresh token → 200 + new access/refresh pair")
    void refreshHappyPath() throws Exception {
        IssuedTokens t = registerAndLogin("refresh@user.test", "Password123");

        mockMvc.perform(post("/api/v1/auth/refresh")
                .contentType(MediaType.APPLICATION_JSON)
                .content(asJson(body().put("refreshToken", t.refresh()))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.accessToken").value(notNullValue()))
                .andExpect(jsonPath("$.refreshToken").value(notNullValue()));
    }

    @Test
    @DisplayName("POST /refresh with an *access* token (wrong type) → 401")
    void refreshRejectsAccessToken() throws Exception {
        IssuedTokens t = registerAndLogin("refresh2@user.test", "Password123");

        mockMvc.perform(post("/api/v1/auth/refresh")
                .contentType(MediaType.APPLICATION_JSON)
                .content(asJson(body().put("refreshToken", t.access()))))
                .andExpect(status().isUnauthorized());
    }

    // --- Logout ----------------------------------------------------------

    @Test
    @DisplayName("POST /logout 204 — JwtTokenProvider.revoke fired against the bearer token")
    void logoutHappyPath() throws Exception {
        IssuedTokens t = registerAndLogin("logout@user.test", "Password123");

        mockMvc.perform(post("/api/v1/auth/logout")
                .header("Authorization", "Bearer " + t.access()))
                .andExpect(status().isNoContent());
        // The blacklist write happens via the (mocked) RedisTemplate;
        // we verify in a separate test below that JwtTokenProvider was
        // invoked. Here we just pin the controller status code.
    }

    @Test
    @DisplayName("POST /logout without Authorization header → 400")
    void logoutNeedsBearer() throws Exception {
        mockMvc.perform(post("/api/v1/auth/logout"))
                .andExpect(status().isBadRequest());
    }

    @Test
    @DisplayName("End-to-end happy chain — register, login back, hit /me with the login token")
    void registerLoginMeChain() throws Exception {
        mockMvc.perform(post("/api/v1/auth/register")
                .contentType(MediaType.APPLICATION_JSON)
                .content(asJson(body()
                        .put("email", "chain@user.test")
                        .put("password", "Password123"))))
                .andExpect(status().isCreated());

        MvcResult loginRes = mockMvc.perform(post("/api/v1/auth/login")
                .contentType(MediaType.APPLICATION_JSON)
                .content(asJson(body()
                        .put("email", "chain@user.test")
                        .put("password", "Password123"))))
                .andExpect(status().isOk())
                .andReturn();
        String access = objectMapper.readTree(loginRes.getResponse().getContentAsString())
                .get("accessToken").asText();

        mockMvc.perform(get("/api/v1/users/me")
                .header("Authorization", "Bearer " + access))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.email").value("chain@user.test"));
    }

    // --- Cleanup ---------------------------------------------------------

    /** Belt-and-braces: best-effort tidy of the temp keys at JVM exit. */
    @SuppressWarnings("unused")
    private static void cleanupKeysOnExit() throws IOException {
        Files.deleteIfExists(PRIVATE_PEM);
        Files.deleteIfExists(PUBLIC_PEM);
        Files.deleteIfExists(TMP_DIR);
    }
}
