package com.wcp.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.wcp.config.WcpProperties;
import com.wcp.dto.response.PaymentInitResponse;
import com.wcp.dto.response.SubscriptionPlanResponse;
import com.wcp.exception.PaymentChannelDisabledException;
import com.wcp.model.Payment;
import com.wcp.model.User;
import com.wcp.payment.StripeClient;
import com.wcp.repository.PaymentRepository;
import com.wcp.repository.UserRepository;
import java.util.UUID;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

/**
 * Behaviour of the {@code wcp.payments.enable-cn-channels} feature flag.
 *
 * Background: PaymentService.verifySignature is a stub (Phase-3 leftover)
 * that accepts any non-empty payload. Exposing the Alipay / WeChat
 * callback endpoint to the public internet would let an attacker replay
 * a hand-crafted POST and flip an existing `pending` Payment row to
 * `paid`. The flag gates both the order-creation path AND the callback
 * endpoint so production keeps a small attack surface until the real
 * SDKs land.
 */
@ExtendWith(MockitoExtension.class)
class CnPaymentChannelsTest {

    @Mock private PaymentRepository paymentRepository;
    @Mock private UserRepository userRepository;
    @Mock private SubscriptionService subscriptionService;
    @Mock private StripeClient stripeClient;
    @Mock private WcpProperties wcpProperties;

    @InjectMocks private PaymentService paymentService;

    private User stubUser() {
        return User.builder()
                .id(1L).uuid(UUID.randomUUID())
                .email("u@u.test").passwordHash("h")
                .subscriptionTier("free").locale("zh-CN").timezone("Asia/Shanghai")
                .active(true).role("user")
                .build();
    }

    private Payment alipayOrder() {
        return Payment.builder()
                .id(1L).userId(1L).orderNo("WCP-CN-1")
                .paymentChannel("alipay").amountCny(7193).status("pending")
                .build();
    }

    private Payment wechatOrder() {
        return Payment.builder()
                .id(2L).userId(1L).orderNo("WCP-CN-2")
                .paymentChannel("wechat_pay").amountCny(7193).status("pending")
                .build();
    }

    private SubscriptionPlanResponse plan() {
        return new SubscriptionPlanResponse(
                "basic", "monthly", 999, 7193, 30, "Basic · Monthly"
        );
    }

    private void setCnChannelsEnabled(boolean enabled) {
        when(wcpProperties.payments())
                .thenReturn(new WcpProperties.Payments(enabled));
    }

    // ---------------------------------------------------------------------
    // Flag OFF: production default
    // ---------------------------------------------------------------------

    @Nested
    @DisplayName("flag OFF (production default)")
    class CnChannelsDisabled {

        @Test
        @DisplayName("initPayment(alipay) → PaymentChannelDisabledException + 503")
        void alipayOrderRejected() {
            setCnChannelsEnabled(false);

            assertThatThrownBy(() ->
                    paymentService.initPayment(alipayOrder(), plan(), stubUser())
            )
                    .isInstanceOf(PaymentChannelDisabledException.class)
                    .satisfies(ex -> {
                        PaymentChannelDisabledException e = (PaymentChannelDisabledException) ex;
                        assertThat(e.getStatus().value()).isEqualTo(503);
                        assertThat(e.getChannel()).isEqualTo("alipay");
                    });

            // Defensive: no DB writes or subscription grants when the channel is off.
            verify(paymentRepository, never()).save(any());
            verify(subscriptionService, never()).activateSubscription(any(), any(), any());
        }

        @Test
        @DisplayName("initPayment(wechat_pay) → PaymentChannelDisabledException + 503")
        void wechatOrderRejected() {
            setCnChannelsEnabled(false);

            assertThatThrownBy(() ->
                    paymentService.initPayment(wechatOrder(), plan(), stubUser())
            )
                    .isInstanceOf(PaymentChannelDisabledException.class);
        }

        @Test
        @DisplayName("isCnChannelsEnabled returns false")
        void probeReturnsFalse() {
            setCnChannelsEnabled(false);
            assertThat(paymentService.isCnChannelsEnabled()).isFalse();
        }

        @Test
        @DisplayName("payments() returning null is treated as disabled (safe default)")
        void nullPaymentsRecordIsDisabled() {
            when(wcpProperties.payments()).thenReturn(null);
            assertThat(paymentService.isCnChannelsEnabled()).isFalse();
        }
    }

    // ---------------------------------------------------------------------
    // Flag ON: dev profile
    // ---------------------------------------------------------------------

    @Nested
    @DisplayName("flag ON (dev profile)")
    class CnChannelsEnabled {

        @Test
        @DisplayName("initPayment(alipay) succeeds + returns stub-marker sdkPayload")
        void alipayOrderSucceeds() {
            setCnChannelsEnabled(true);

            PaymentInitResponse out = paymentService.initPayment(alipayOrder(), plan(), stubUser());

            assertThat(out.paymentChannel()).isEqualTo("alipay");
            assertThat(out.amountUsd()).isEqualTo(999);
            assertThat(out.amountCny()).isEqualTo(7193);

            @SuppressWarnings("unchecked")
            java.util.Map<String, Object> sdk =
                    (java.util.Map<String, Object>) out.paymentParams().get("sdkPayload");
            assertThat(sdk).containsEntry("mode", "stub")
                    .containsEntry("reason", "cn_channel_sdk_not_integrated");
        }

        @Test
        @DisplayName("isCnChannelsEnabled returns true")
        void probeReturnsTrue() {
            setCnChannelsEnabled(true);
            assertThat(paymentService.isCnChannelsEnabled()).isTrue();
        }
    }
}
