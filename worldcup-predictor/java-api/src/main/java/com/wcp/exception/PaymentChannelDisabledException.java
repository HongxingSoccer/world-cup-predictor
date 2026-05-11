package com.wcp.exception;

import org.springframework.http.HttpStatus;

/**
 * Raised when an order targets a payment channel that is currently disabled
 * in this environment (e.g. Alipay / WeChat Pay before their SDKs ship).
 *
 * <p>Mapped to HTTP 503 by the global exception handler so the caller knows
 * to retry later with a different channel (Stripe in this case) rather than
 * treating it as a permanent failure.
 */
public class PaymentChannelDisabledException extends ApiException {

    public PaymentChannelDisabledException(String channel) {
        super(
                HttpStatus.SERVICE_UNAVAILABLE,
                50301,
                "PAYMENT_CHANNEL_UNAVAILABLE",
                "CN payment channels are disabled in this environment: " + channel
        );
        this.channel = channel;
    }

    private final String channel;

    public String getChannel() {
        return channel;
    }
}
