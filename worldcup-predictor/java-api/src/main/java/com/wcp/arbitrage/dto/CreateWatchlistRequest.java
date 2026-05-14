package com.wcp.arbitrage.dto;

import jakarta.validation.constraints.DecimalMin;
import java.math.BigDecimal;
import java.util.List;

public record CreateWatchlistRequest(
        Long competitionId,
        List<String> marketTypes,
        @DecimalMin(value = "0", inclusive = true) BigDecimal minProfitMargin,
        Boolean notifyEnabled
) {}
