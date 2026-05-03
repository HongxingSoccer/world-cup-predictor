package com.wcp.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record CreateShareLinkRequest(
        @NotBlank @Pattern(regexp = "prediction|match|track_record") String targetType,
        Long targetId,
        @NotBlank String targetUrl,
        @Size(max = 50) String utmSource,
        @Size(max = 50) String utmMedium,
        @Size(max = 100) String utmCampaign
) {}
