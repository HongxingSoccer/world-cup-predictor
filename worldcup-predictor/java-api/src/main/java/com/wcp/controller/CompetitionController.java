package com.wcp.controller;

import com.wcp.client.MlApiClient;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import java.util.Map;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Thin proxy for the public competition endpoints. The heavy lifting
 * (group derivation, standings computation, bracket bucketing) happens in
 * the Python ML API, which has full ORM access; this controller just
 * surfaces it under the /api/v1/competitions/* namespace served by nginx.
 */
@RestController
@RequiredArgsConstructor
@Tag(name = "competitions", description = "Public groups standings + knockout bracket views.")
public class CompetitionController {

    private final MlApiClient mlApiClient;

    @GetMapping("/api/v1/competitions/worldcup/standings")
    @Operation(summary = "FIFA World Cup group-stage standings derived from ingested fixtures.")
    public ResponseEntity<Map<String, Object>> worldcupStandings() {
        return ResponseEntity.ok(mlApiClient.worldcupStandings());
    }

    @GetMapping("/api/v1/competitions/worldcup/bracket")
    @Operation(summary = "FIFA World Cup knockout bracket scaffold + scheduled matches.")
    public ResponseEntity<Map<String, Object>> worldcupBracket() {
        return ResponseEntity.ok(mlApiClient.worldcupBracket());
    }

    @GetMapping("/api/v1/competitions/worldcup/simulation")
    @Operation(summary = "FIFA World Cup tournament Monte Carlo: champion / top-4 / qualify probabilities.")
    public ResponseEntity<Map<String, Object>> worldcupSimulation() {
        return ResponseEntity.ok(mlApiClient.worldcupSimulation());
    }
}
