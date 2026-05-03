package com.wcp.dto.response;

public record ShareLinkResponse(
        String shortCode,
        String shareUrl,
        Long shareLinkId,
        long clickCount,
        long registerCount,
        long subscribeCount
) {}
