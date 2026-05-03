package com.wcp.controller;

import com.fasterxml.jackson.databind.JsonNode;
import com.wcp.dto.request.CreateSubscriptionRequest;
import com.wcp.dto.response.PaymentInitResponse;
import com.wcp.dto.response.SubscriptionPlanResponse;
import com.wcp.exception.ApiException;
import com.wcp.model.Subscription;
import com.wcp.security.UserPrincipal;
import com.wcp.service.PaymentService;
import com.wcp.service.SubscriptionService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import java.util.List;
import java.util.Map;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@Tag(name = "subscriptions", description = "Pricing catalogue, order creation, payment callbacks.")
public class SubscriptionController {

    private final SubscriptionService subscriptionService;
    private final PaymentService paymentService;

    @GetMapping("/api/v1/subscriptions/plans")
    @Operation(summary = "Available subscription plans (basic/premium × monthly/worldcup_pass).")
    public ResponseEntity<List<SubscriptionPlanResponse>> plans() {
        return ResponseEntity.ok(subscriptionService.plans());
    }

    @PostMapping("/api/v1/subscriptions/create")
    @Operation(summary = "Create a pending payment + return SDK params.")
    public ResponseEntity<PaymentInitResponse> create(
            @AuthenticationPrincipal UserPrincipal principal,
            @Valid @RequestBody CreateSubscriptionRequest req
    ) {
        if (principal == null) {
            throw ApiException.unauthorized("login required");
        }
        return ResponseEntity.ok(subscriptionService.createSubscription(principal, req));
    }

    @GetMapping("/api/v1/subscriptions/current")
    @Operation(summary = "Currently-active subscription window for the caller.")
    public ResponseEntity<Map<String, Object>> current(
            @AuthenticationPrincipal UserPrincipal principal) {
        if (principal == null) {
            throw ApiException.unauthorized("login required");
        }
        Subscription sub = subscriptionService.currentSubscription(principal).orElse(null);
        if (sub == null) {
            return ResponseEntity.ok(Map.of("active", false, "tier", "free"));
        }
        return ResponseEntity.ok(Map.of(
                "active", true,
                "tier", sub.getTier(),
                "planType", sub.getPlanType(),
                "expiresAt", sub.getExpiresAt(),
                "autoRenew", sub.isAutoRenew()
        ));
    }

    @PostMapping("/api/v1/subscriptions/cancel")
    @Operation(summary = "Disable auto-renew on the current subscription.")
    public ResponseEntity<Void> cancel(@AuthenticationPrincipal UserPrincipal principal) {
        if (principal == null) {
            throw ApiException.unauthorized("login required");
        }
        subscriptionService.cancelAutoRenew(principal);
        return ResponseEntity.noContent().build();
    }

    // --- Payment callback endpoints (no auth — verified by signature) ---

    @PostMapping("/api/v1/payments/callback/{channel}")
    @Operation(summary = "Async payment callback (Alipay / WeChat).")
    public ResponseEntity<String> paymentCallback(
            @PathVariable String channel,
            @RequestBody JsonNode payload
    ) {
        if (!"alipay".equals(channel) && !"wechat_pay".equals(channel)) {
            throw ApiException.badRequest("unknown channel: " + channel);
        }
        paymentService.handleCallback(channel, payload);
        // Both providers expect `success` as the canonical ack body.
        return ResponseEntity.ok("success");
    }
}
