package com.wcp.model;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.persistence.*;
import java.time.Instant;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.annotations.UpdateTimestamp;
import org.hibernate.type.SqlTypes;

/**
 * Single source of truth for every paid transaction.
 *
 * <p>{@code callbackRaw} stores the verbatim payment-provider callback so we
 * can audit / reconcile if a chargeback dispute lands; it's a generic
 * {@link JsonNode} rather than a typed DTO since the two providers'
 * payloads diverge in non-trivial ways.
 */
@Entity
@Table(name = "payments")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder(toBuilder = true)
public class Payment {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id", nullable = false)
    private Long userId;

    @Column(name = "order_no", length = 64, nullable = false, unique = true)
    private String orderNo;

    @Column(name = "payment_channel", length = 20, nullable = false)
    private String paymentChannel;

    @Column(name = "amount_cny", nullable = false)
    private Integer amountCny;

    @Setter
    @Column(length = 20, nullable = false)
    @Builder.Default
    private String status = "pending";

    @Setter
    @Column(name = "channel_trade_no", length = 100)
    private String channelTradeNo;

    @Setter
    @Column(name = "paid_at")
    private Instant paidAt;

    @Setter
    @Column(name = "refunded_at")
    private Instant refundedAt;

    @Setter
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "callback_raw", columnDefinition = "jsonb")
    private JsonNode callbackRaw;

    @Setter
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(columnDefinition = "jsonb")
    private JsonNode meta;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @UpdateTimestamp
    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    public boolean isPaid() {
        return "paid".equals(this.status);
    }
}
