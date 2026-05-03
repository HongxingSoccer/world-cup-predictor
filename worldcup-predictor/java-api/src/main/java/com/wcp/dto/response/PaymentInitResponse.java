package com.wcp.dto.response;

import java.util.Map;

/**
 * Payload returned by /subscriptions/create. The {@code paymentParams} are
 * an opaque map handed back to the front-end which forwards them to the
 * Alipay / WeChat SDK to actually launch the cashier.
 */
public record PaymentInitResponse(
        String orderNo,
        String paymentChannel,
        int amountCny,
        Map<String, Object> paymentParams
) {}
