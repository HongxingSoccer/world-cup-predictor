package com.wcp.arbitrage;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.wcp.arbitrage.dto.CreateWatchlistRequest;
import com.wcp.arbitrage.dto.WatchlistResponse;
import com.wcp.arbitrage.entity.ArbWatchlistEntity;
import com.wcp.exception.ApiException;
import com.wcp.security.UserPrincipal;
import java.math.BigDecimal;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Owner of the per-user arbitrage-watchlist rules.
 *
 * <p>Pure JPA. The Python {@code arb-scanner-worker} is the canonical
 * reader — it pulls every {@code notify_enabled} row each scan tick and
 * matches against newly-detected opportunities.
 */
@Service
@RequiredArgsConstructor
public class ArbWatchlistService {

    private static final BigDecimal DEFAULT_MIN_MARGIN = new BigDecimal("0.01");

    private final ArbWatchlistRepository repo;
    private final ObjectMapper objectMapper;

    @Transactional(readOnly = true)
    public List<WatchlistResponse> list(UserPrincipal principal) {
        requireLogin(principal);
        return repo.findByUserIdOrderByCreatedAtDesc(principal.id())
                .stream()
                .map(WatchlistResponse::from)
                .toList();
    }

    @Transactional
    public WatchlistResponse create(UserPrincipal principal, CreateWatchlistRequest req) {
        requireLogin(principal);
        ArbWatchlistEntity entity = ArbWatchlistEntity.builder()
                .userId(principal.id())
                .competitionId(req.competitionId())
                .marketTypes(toJsonArray(req.marketTypes()))
                .minProfitMargin(req.minProfitMargin() != null
                        ? req.minProfitMargin()
                        : DEFAULT_MIN_MARGIN)
                .notifyEnabled(req.notifyEnabled() == null || req.notifyEnabled())
                .build();
        return WatchlistResponse.from(repo.save(entity));
    }

    @Transactional
    public void delete(UserPrincipal principal, Long id) {
        requireLogin(principal);
        ArbWatchlistEntity row = repo.findByIdAndUserId(id, principal.id())
                .orElseThrow(() -> ApiException.notFound("watchlist " + id));
        repo.delete(row);
    }

    private static void requireLogin(UserPrincipal principal) {
        if (principal == null || principal.id() == null) {
            throw ApiException.unauthorized("login required");
        }
    }

    private JsonNode toJsonArray(List<String> values) {
        if (values == null || values.isEmpty()) {
            return null;
        }
        ArrayNode arr = objectMapper.createArrayNode();
        values.forEach(arr::add);
        return arr;
    }
}
