package com.wcp.integration;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.wcp.client.MlApiClient;
import com.wcp.payment.StripeClient;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.util.Base64;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.jdbc.AutoConfigureTestDatabase;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.transaction.annotation.Transactional;

/**
 * Shared scaffolding for every @SpringBootTest in this package:
 *
 * <ul>
 *   <li>Generates a temp RSA key-pair at class load time and feeds the
 *       paths into the Spring context via {@link DynamicPropertySource}.
 *       Without it the JwtTokenProvider {@code @PostConstruct} blows up
 *       trying to read the production secret paths.</li>
 *   <li>Mocks the three external integrations that controllers brush
 *       against: the Python ml-api client, the Stripe SDK wrapper, and
 *       the Redis blacklist used by JWT logout. The test profile
 *       ({@code application-test.yml}) excludes Redis auto-config so the
 *       mock satisfies the only dependency the production code needs.</li>
 * </ul>
 *
 * Subclasses just declare their own test methods + any extra mocks they
 * need. Each test method runs in its own transaction (rolled back at the
 * end) so writes don't bleed between tests.
 */
@SpringBootTest
@AutoConfigureMockMvc
@AutoConfigureTestDatabase(replace = AutoConfigureTestDatabase.Replace.NONE)
@ActiveProfiles("test")
@Transactional
public abstract class IntegrationTestBase {

    protected static final Path TMP_DIR;
    protected static final Path PRIVATE_PEM;
    protected static final Path PUBLIC_PEM;

    static {
        try {
            TMP_DIR = Files.createTempDirectory("wcp-it-keys-");
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

    @Autowired protected MockMvc mockMvc;
    @Autowired protected ObjectMapper objectMapper;

    @MockBean protected MlApiClient mlApiClient;
    @MockBean protected StripeClient stripeClient;
    @MockBean(name = "redisTemplate") @SuppressWarnings("rawtypes")
    protected RedisTemplate redisTemplate;
}
