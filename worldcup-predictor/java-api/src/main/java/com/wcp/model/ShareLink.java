package com.wcp.model;

import jakarta.persistence.*;
import java.time.Instant;
import lombok.AccessLevel;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.CreationTimestamp;

/** Short-link with embedded UTM + per-funnel-stage counters. */
@Entity
@Table(name = "share_links")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@AllArgsConstructor
@Builder
public class ShareLink {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Setter
    @Column(name = "short_code", length = 10, nullable = false, unique = true)
    private String shortCode;

    @Column(name = "user_id")
    private Long userId;

    @Column(name = "target_type", length = 20, nullable = false)
    private String targetType;

    @Column(name = "target_id")
    private Long targetId;

    @Column(name = "target_url", columnDefinition = "TEXT", nullable = false)
    private String targetUrl;

    @Column(name = "utm_source", length = 50)
    private String utmSource;

    @Column(name = "utm_medium", length = 50)
    private String utmMedium;

    @Column(name = "utm_campaign", length = 100)
    private String utmCampaign;

    @Setter
    @Column(name = "click_count", nullable = false)
    @Builder.Default
    private Integer clickCount = 0;

    @Setter
    @Column(name = "register_count", nullable = false)
    @Builder.Default
    private Integer registerCount = 0;

    @Setter
    @Column(name = "subscribe_count", nullable = false)
    @Builder.Default
    private Integer subscribeCount = 0;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    public void incrementClicks() {
        this.clickCount = this.clickCount + 1;
    }
}
