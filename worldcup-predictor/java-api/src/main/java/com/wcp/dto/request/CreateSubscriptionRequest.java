package com.wcp.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;

public record CreateSubscriptionRequest(
        @NotBlank @Pattern(regexp = "basic|premium") String tier,
        @NotBlank @Pattern(regexp = "monthly|worldcup_pass") String planType,
        @NotBlank @Pattern(regexp = "alipay|wechat_pay") String paymentChannel
) {}
