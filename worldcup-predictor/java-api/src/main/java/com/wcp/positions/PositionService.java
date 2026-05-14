package com.wcp.positions;

import com.wcp.exception.ApiException;
import com.wcp.positions.dto.CreatePositionRequest;
import com.wcp.positions.dto.PositionResponse;
import com.wcp.positions.dto.UpdateStatusRequest;
import com.wcp.positions.entity.PositionEntity;
import com.wcp.security.UserPrincipal;
import java.util.List;
import java.util.Set;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Owner of the user-position lifecycle on the Java side.
 *
 * <p>Pure JPA — does not call ml-api. The Python {@code live_monitor} worker
 * is responsible for the opportunity-detection side; here we only handle
 * the CRUD ops a user can drive from the Next.js UI.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class PositionService {

    private static final Set<String> VALID_STATUSES =
            Set.of("active", "hedged", "settled", "cancelled");
    private static final Set<String> VALID_MARKETS =
            Set.of("1x2", "over_under", "asian_handicap", "btts");

    private final PositionRepository repo;

    @Transactional
    public PositionResponse create(UserPrincipal principal, CreatePositionRequest req) {
        requireLogin(principal);
        validateMarket(req.market());

        PositionEntity entity = PositionEntity.builder()
                .userId(principal.id())
                .matchId(req.matchId())
                .platform(req.platform())
                .market(req.market())
                .outcome(req.outcome())
                .stake(req.stake())
                .odds(req.odds())
                .placedAt(req.placedAt())
                .notes(req.notes())
                .build();
        return PositionResponse.from(repo.save(entity));
    }

    @Transactional(readOnly = true)
    public List<PositionResponse> list(UserPrincipal principal, String status) {
        requireLogin(principal);
        List<PositionEntity> rows = (status == null || status.isBlank())
                ? repo.findByUserIdOrderByCreatedAtDesc(principal.id())
                : repo.findByUserIdAndStatusOrderByCreatedAtDesc(principal.id(), status);
        return rows.stream().map(PositionResponse::from).toList();
    }

    @Transactional(readOnly = true)
    public PositionResponse get(UserPrincipal principal, Long id) {
        return PositionResponse.from(mustOwn(principal, id));
    }

    @Transactional
    public PositionResponse updateStatus(
            UserPrincipal principal, Long id, UpdateStatusRequest req) {
        if (!VALID_STATUSES.contains(req.status())) {
            throw ApiException.badRequest("unsupported status: " + req.status());
        }
        PositionEntity entity = mustOwn(principal, id);
        entity.setStatus(req.status());
        return PositionResponse.from(entity);
    }

    @Transactional
    public PositionResponse softDelete(UserPrincipal principal, Long id) {
        PositionEntity entity = mustOwn(principal, id);
        entity.setStatus("cancelled");
        return PositionResponse.from(entity);
    }

    // ------------------------------------------------------------------
    // Helpers
    // ------------------------------------------------------------------

    private static void requireLogin(UserPrincipal principal) {
        if (principal == null || principal.id() == null) {
            throw ApiException.unauthorized("login required");
        }
    }

    private static void validateMarket(String market) {
        if (!VALID_MARKETS.contains(market)) {
            throw ApiException.badRequest("unsupported market: " + market);
        }
    }

    private PositionEntity mustOwn(UserPrincipal principal, Long id) {
        requireLogin(principal);
        return repo.findByIdAndUserId(id, principal.id())
                .orElseThrow(() -> ApiException.notFound("position " + id));
    }
}
