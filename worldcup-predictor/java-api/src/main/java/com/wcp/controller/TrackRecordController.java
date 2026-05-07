package com.wcp.controller;

import com.wcp.dto.response.TrackRecordOverviewResponse;
import com.wcp.service.TrackRecordService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/** Public scoreboard. All endpoints permitAll'd in {@link com.wcp.config.SecurityConfig}. */
@RestController
@RequestMapping("/api/v1/track-record")
@RequiredArgsConstructor
@Tag(name = "track-record", description = "Public hit-rate / ROI / streak scoreboard.")
public class TrackRecordController {

    private final TrackRecordService trackRecordService;

    @GetMapping("/overview")
    @Operation(summary = "Overall stat for a stat-type / period combo.")
    public ResponseEntity<TrackRecordOverviewResponse> overview(
            @RequestParam(defaultValue = "overall") String statType,
            @RequestParam(defaultValue = "all_time") String period
    ) {
        // Pre-tournament the table is genuinely empty. Return a zero default
        // (200 OK) instead of 404 so the frontend can render its
        // "data lands once the tournament starts" empty state instead of
        // a broken page.
        return ResponseEntity.ok(
                trackRecordService.overview(statType, period)
                        .orElseGet(() -> zeroOverview(statType, period))
        );
    }

    private static TrackRecordOverviewResponse zeroOverview(String statType, String period) {
        return new TrackRecordOverviewResponse(
                statType,
                period,
                0,
                0,
                BigDecimal.ZERO,
                BigDecimal.ZERO,
                BigDecimal.ZERO,
                0,
                0,
                Instant.EPOCH
        );
    }

    @GetMapping("/roi-chart")
    @Operation(summary = "All stat types for one period — drives the ROI dashboard.")
    public ResponseEntity<List<TrackRecordOverviewResponse>> roiChart(
            @RequestParam(defaultValue = "all_time") String period
    ) {
        return ResponseEntity.ok(trackRecordService.overviewByPeriod(period));
    }

    @GetMapping("/by-market/{type}")
    @Operation(summary = "Per-market stats (1x2 / score / ou25 / btts / positive_ev).")
    public ResponseEntity<List<TrackRecordOverviewResponse>> byMarket(
            @PathVariable String type
    ) {
        // Re-use the per-period collection then filter to the requested market.
        List<TrackRecordOverviewResponse> all = trackRecordService.overviewByPeriod("all_time");
        return ResponseEntity.ok(
                all.stream().filter(r -> type.equals(r.statType())).toList()
        );
    }

    @GetMapping("/history")
    @Operation(summary = "Phase 3.5 stub — paged historical predictions.")
    public ResponseEntity<List<TrackRecordOverviewResponse>> history(
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size
    ) {
        // TODO(Phase 3.5): paged join over prediction_results + matches.
        return ResponseEntity.ok(List.of());
    }
}
