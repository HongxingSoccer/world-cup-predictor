package com.wcp.service;

import com.wcp.dto.response.TrackRecordOverviewResponse;
import com.wcp.model.TrackRecordStat;
import com.wcp.repository.TrackRecordStatRepository;
import java.time.Duration;
import java.util.List;
import java.util.Optional;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

/**
 * Public-scoreboard read service. Two layers of caching:
 *
 *   1. Redis (TTL 10 min) — keyed on the same `(stat_type, period)` pair as
 *      the underlying row, so cache hits don't span filters.
 *   2. The database row itself, kept warm by the settlement task. We never
 *      compute live aggregates here — the response is read-only.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class TrackRecordService {

    private static final Duration CACHE_TTL = Duration.ofMinutes(10);
    private static final String CACHE_PREFIX = "wcp:track:";

    private final TrackRecordStatRepository statRepository;
    private final RedisTemplate<String, Object> redisTemplate;

    public Optional<TrackRecordOverviewResponse> overview(String statType, String period) {
        String key = CACHE_PREFIX + statType + ":" + period;
        Object cached = safeGet(key);
        if (cached instanceof TrackRecordOverviewResponse hit) {
            return Optional.of(hit);
        }
        return statRepository.findByStatTypeAndPeriod(statType, period)
                .map(TrackRecordService::toResponse)
                .map(resp -> {
                    safeSet(key, resp);
                    return resp;
                });
    }

    public List<TrackRecordOverviewResponse> overviewByPeriod(String period) {
        return statRepository.findByPeriod(period).stream()
                .map(TrackRecordService::toResponse)
                .toList();
    }

    private static TrackRecordOverviewResponse toResponse(TrackRecordStat row) {
        return new TrackRecordOverviewResponse(
                row.getStatType(),
                row.getPeriod(),
                row.getTotalPredictions(),
                row.getHits(),
                row.getHitRate(),
                row.getTotalPnlUnits(),
                row.getRoi(),
                row.getCurrentStreak(),
                row.getBestStreak(),
                row.getUpdatedAt()
        );
    }

    private Object safeGet(String key) {
        try {
            return redisTemplate.opsForValue().get(key);
        } catch (Exception ex) {
            log.debug("redis_unavailable_skip_cache key={}", key);
            return null;
        }
    }

    private void safeSet(String key, Object value) {
        try {
            redisTemplate.opsForValue().set(key, value, CACHE_TTL);
        } catch (Exception ex) {
            log.debug("redis_unavailable_skip_cache_write key={}", key);
        }
    }
}
