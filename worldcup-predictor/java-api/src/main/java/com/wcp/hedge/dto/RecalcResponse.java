package com.wcp.hedge.dto;

import java.util.List;

/** Lightweight response for {@code POST /scenarios/{id}/recalc}. */
public record RecalcResponse(
        Long scenarioId,
        int oldCalculationCount,
        int newCalculationCount,
        List<ScenarioResponse.CalculationDto> calculations,
        String disclaimer
) {}
