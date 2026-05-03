package com.wcp.controller;

import com.wcp.dto.request.CreateShareLinkRequest;
import com.wcp.dto.response.ShareLinkResponse;
import com.wcp.security.UserPrincipal;
import com.wcp.service.ShareService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import java.net.URI;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@Tag(name = "share", description = "Short-link create + redirect + stats.")
public class ShareController {

    private final ShareService shareService;

    @PostMapping("/api/v1/share/create")
    @Operation(summary = "Create a tracked short link for the given target.")
    public ResponseEntity<ShareLinkResponse> create(
            @AuthenticationPrincipal UserPrincipal principal,
            @Valid @RequestBody CreateShareLinkRequest req
    ) {
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(shareService.createLink(principal, req));
    }

    @GetMapping("/s/{shortCode}")
    @Operation(summary = "Resolve and 302-redirect a short code; click is counted.")
    public ResponseEntity<Void> redirect(@PathVariable String shortCode) {
        String target = shareService.resolveAndCount(shortCode);
        return ResponseEntity.status(HttpStatus.FOUND).location(URI.create(target)).build();
    }

    @GetMapping("/api/v1/share/{id}/stats")
    @Operation(summary = "Counters for one short link (clicks / registers / subscribes).")
    public ResponseEntity<ShareLinkResponse> stats(@PathVariable long id) {
        return ResponseEntity.ok(shareService.stats(id));
    }
}
