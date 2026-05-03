package com.wcp.service;

import com.wcp.config.WcpProperties;
import com.wcp.dto.request.CreateShareLinkRequest;
import com.wcp.dto.response.ShareLinkResponse;
import com.wcp.exception.ApiException;
import com.wcp.model.ShareLink;
import com.wcp.repository.ShareLinkRepository;
import com.wcp.security.UserPrincipal;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Short-link create + redirect.
 *
 * <p>{@code short_code} is the Base62 encoding of the row id. We create the
 * row first to get an id, then encode + persist it. Database UNIQUE on
 * {@code short_code} guards against any (extremely unlikely) collisions.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class ShareService {

    private static final String BASE62 =
            "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";

    private final ShareLinkRepository repository;
    private final WcpProperties wcpProperties;

    @Transactional
    public ShareLinkResponse createLink(UserPrincipal principal, CreateShareLinkRequest req) {
        ShareLink draft = ShareLink.builder()
                .userId(principal == null ? null : principal.id())
                .targetType(req.targetType())
                .targetId(req.targetId())
                .targetUrl(req.targetUrl())
                .utmSource(req.utmSource())
                .utmMedium(req.utmMedium())
                .utmCampaign(req.utmCampaign())
                .clickCount(0)
                .registerCount(0)
                .subscribeCount(0)
                // Placeholder; replaced below once the row has an id.
                .shortCode("pending")
                .build();
        // First save assigns the id (autoincrement) but the placeholder code
        // doesn't satisfy uniqueness once a second row collides; we update
        // immediately afterwards inside the same transaction.
        ShareLink persisted = repository.save(draft);
        persisted.setShortCode(toBase62(persisted.getId()));
        persisted = repository.save(persisted);

        return new ShareLinkResponse(
                persisted.getShortCode(),
                wcpProperties.share().baseUrl() + persisted.getShortCode(),
                persisted.getId(),
                persisted.getClickCount(),
                persisted.getRegisterCount(),
                persisted.getSubscribeCount()
        );
    }

    @Transactional
    public String resolveAndCount(String shortCode) {
        ShareLink link = repository.findByShortCode(shortCode)
                .orElseThrow(() -> ApiException.notFound("share link"));
        repository.incrementClicks(link.getId());
        return link.getTargetUrl();
    }

    public ShareLinkResponse stats(long id) {
        ShareLink link = repository.findById(id)
                .orElseThrow(() -> ApiException.notFound("share link"));
        return new ShareLinkResponse(
                link.getShortCode(),
                wcpProperties.share().baseUrl() + link.getShortCode(),
                link.getId(),
                link.getClickCount(),
                link.getRegisterCount(),
                link.getSubscribeCount()
        );
    }

    static String toBase62(long value) {
        if (value == 0) {
            return "0";
        }
        StringBuilder sb = new StringBuilder();
        long n = value;
        while (n > 0) {
            sb.append(BASE62.charAt((int) (n % 62)));
            n /= 62;
        }
        return sb.reverse().toString();
    }
}
