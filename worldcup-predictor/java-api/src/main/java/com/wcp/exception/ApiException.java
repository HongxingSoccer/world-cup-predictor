package com.wcp.exception;

import lombok.Getter;
import org.springframework.http.HttpStatus;

/**
 * Base exception with an HTTP-status hint + machine-readable error code.
 *
 * <p>Specific cases sub-class this (UserNotFound, SubscriptionExpired, …).
 * The {@link com.wcp.exception.GlobalExceptionHandler} maps every subclass
 * to the project-standard JSON error envelope.
 */
@Getter
public class ApiException extends RuntimeException {

    private final HttpStatus status;
    private final int code;
    private final String error;

    public ApiException(HttpStatus status, int code, String error, String message) {
        super(message);
        this.status = status;
        this.code = code;
        this.error = error;
    }

    public static ApiException notFound(String resource) {
        return new ApiException(HttpStatus.NOT_FOUND, 40400, "NOT_FOUND", resource + " not found");
    }

    public static ApiException badRequest(String message) {
        return new ApiException(HttpStatus.BAD_REQUEST, 40000, "BAD_REQUEST", message);
    }

    public static ApiException conflict(String message) {
        return new ApiException(HttpStatus.CONFLICT, 40900, "CONFLICT", message);
    }

    public static ApiException unauthorized(String message) {
        return new ApiException(HttpStatus.UNAUTHORIZED, 40100, "UNAUTHORIZED", message);
    }

    public static ApiException forbidden(String message) {
        return new ApiException(HttpStatus.FORBIDDEN, 40300, "FORBIDDEN", message);
    }

    public static ApiException subscriptionExpired() {
        return new ApiException(
                HttpStatus.FORBIDDEN, 40301, "SUBSCRIPTION_EXPIRED",
                "subscription expired or insufficient tier"
        );
    }
}
