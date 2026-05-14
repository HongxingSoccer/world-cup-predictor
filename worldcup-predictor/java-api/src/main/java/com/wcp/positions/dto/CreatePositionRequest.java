package com.wcp.positions.dto;

import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import java.math.BigDecimal;
import java.time.OffsetDateTime;

public record CreatePositionRequest(
        @NotNull Long matchId,
        @NotBlank String platform,
        @NotBlank String market,
        @NotBlank String outcome,
        @NotNull @Positive BigDecimal stake,
        @NotNull @DecimalMin(value = "1.001") BigDecimal odds,
        @NotNull OffsetDateTime placedAt,
        String notes
) {}
