package com.wcp.dto.response;

import java.util.Map;

/**
 * Payload returned by /subscriptions/create. The {@code paymentParams} are
 * an opaque map handed back to the front-end which forwards them to the
 * Alipay / WeChat SDK to actually launch the cashier.
 *
 * <p>Both {@code amountUsd} (display, integer cents) and {@code amountCny}
 * (actual charge, integer fen) are returned. CNY is what the user actually
 * sees on the WeChat / Alipay confirmation screen — USD is for the
 * receipt + history shown back in our own UI.
 */
public record PaymentInitResponse(
        String orderNo,
        String paymentChannel,
        int amountUsd,
        int amountCny,
        Map<String, Object> paymentParams
) {}
