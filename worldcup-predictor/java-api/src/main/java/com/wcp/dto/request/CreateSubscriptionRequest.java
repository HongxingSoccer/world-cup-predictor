package com.wcp.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;

public record CreateSubscriptionRequest(
        @NotBlank @Pattern(regexp = "basic|premium") String tier,
        @NotBlank @Pattern(regexp = "monthly|worldcup_pass") String planType,
        // Stripe was added for international cards; the regex was previously
        // CNY-only and silently 400'd Stripe orders.
        @NotBlank @Pattern(regexp = "alipay|wechat_pay|stripe") String paymentChannel
) {}
