package com.wcp.controller;

import com.wcp.dto.response.UserResponse;
import com.wcp.exception.ApiException;
import com.wcp.security.UserPrincipal;
import com.wcp.service.UserService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import java.util.Map;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/users")
@RequiredArgsConstructor
@Tag(name = "users", description = "Authenticated profile read / update.")
public class UserController {

    private final UserService userService;

    @GetMapping("/me")
    @Operation(summary = "Return the current user's profile.")
    public ResponseEntity<UserResponse> me(@AuthenticationPrincipal UserPrincipal principal) {
        if (principal == null || principal.uuid() == null) {
            throw ApiException.unauthorized("login required");
        }
        return ResponseEntity.ok(UserResponse.from(userService.loadByUuid(principal.uuid())));
    }

    @PutMapping("/me")
    @Operation(summary = "Update the current user's profile fields.")
    public ResponseEntity<UserResponse> updateMe(
            @AuthenticationPrincipal UserPrincipal principal,
            @RequestBody Map<String, String> body
    ) {
        if (principal == null || principal.uuid() == null) {
            throw ApiException.unauthorized("login required");
        }
        return ResponseEntity.ok(UserResponse.from(
                userService.updateProfile(
                        principal.uuid(),
                        body.get("nickname"),
                        body.get("avatarUrl"),
                        body.get("locale"),
                        body.get("timezone")
                )
        ));
    }
}
