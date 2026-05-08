package com.wcp.dto.response;

/**
 * Single line on the pricing page (one row per (tier, plan) combo).
 *
 * <p>Carries both currencies so the frontend can default to USD and only
 * surface the CNY equivalent when the caller picks a Chinese payment
 * channel (Alipay / WeChat). Both values are integer minor units (cents
 * for USD, fen for CNY).
 */
public record SubscriptionPlanResponse(
        String tier,
        String planType,
        int priceUsd,
        int priceCny,
        int durationDays,
        String displayName
) {}
