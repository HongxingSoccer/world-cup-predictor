package com.wcp.dto.response;

/** Single line on the pricing page (one row per (tier, plan) combo). */
public record SubscriptionPlanResponse(
        String tier,
        String planType,
        int priceCny,
        int durationDays,
        String displayName
) {}
