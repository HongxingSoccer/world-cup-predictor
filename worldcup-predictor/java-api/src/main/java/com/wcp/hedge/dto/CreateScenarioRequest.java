package com.wcp.hedge.dto;

import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import java.math.BigDecimal;
import java.util.List;

/**
 * Request body for {@code POST /api/v1/hedge/scenarios}.
 *
 * <p>The controller forwards a normalised version of this to ml-api
 * {@code POST /api/v1/hedge/calculate} (single scenario) or
 * {@code /api/v1/hedge/parlay} (parlay scenario).
 *
 * <p>{@code legs} is required only when {@code scenarioType == "parlay"}.
 * Validation is performed server-side in {@link com.wcp.hedge.HedgeService}.
 */
public record CreateScenarioRequest(
        @NotBlank String scenarioType, // "single" | "parlay"
        Long matchId, // null when scenarioType == "parlay"
        @NotNull @Positive BigDecimal originalStake,
        BigDecimal originalOdds, // required for single
        String originalOutcome, // required for single
        String originalMarket, // required for single
        @NotBlank String hedgeMode, // full | partial | risk
        @DecimalMin("0.0") BigDecimal hedgeRatio, // optional; null → mode-derived
        List<ParlayLegInput> legs // required for parlay
) {

    /** One parlay leg. */
    public record ParlayLegInput(
            @NotNull Long matchId,
            @NotBlank String outcome,
            @NotNull @Positive BigDecimal odds,
            boolean isSettled,
            Boolean isWon
    ) {}
}
