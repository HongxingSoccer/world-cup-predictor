package com.wcp.exception;

import jakarta.validation.ConstraintViolationException;
import java.util.LinkedHashMap;
import java.util.Map;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.AccessDeniedException;
import org.springframework.security.core.AuthenticationException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

/**
 * Centralised mapping from exceptions to the project's error JSON envelope.
 *
 * <p>Envelope is {@code { code, error, message, details? }} per the Phase-2
 * coding standard §7.3. Stack traces never reach the client.
 */
@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {

    @ExceptionHandler(PaymentChannelDisabledException.class)
    public ResponseEntity<Map<String, Object>> onChannelDisabled(PaymentChannelDisabledException ex) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("error", "payment_channel_unavailable");
        body.put("channel", ex.getChannel());
        return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(body);
    }

    @ExceptionHandler(ApiException.class)
    public ResponseEntity<Map<String, Object>> onApi(ApiException ex) {
        return ResponseEntity.status(ex.getStatus()).body(envelope(
                ex.getCode(), ex.getError(), ex.getMessage(), null
        ));
    }

    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<Map<String, Object>> onValidation(MethodArgumentNotValidException ex) {
        return ResponseEntity.badRequest().body(envelope(
                40000, "VALIDATION_ERROR", "request validation failed",
                ex.getBindingResult().getFieldErrors()
        ));
    }

    @ExceptionHandler(ConstraintViolationException.class)
    public ResponseEntity<Map<String, Object>> onConstraint(ConstraintViolationException ex) {
        return ResponseEntity.badRequest().body(envelope(
                40000, "VALIDATION_ERROR", ex.getMessage(), null
        ));
    }

    @ExceptionHandler(AuthenticationException.class)
    public ResponseEntity<Map<String, Object>> onAuth(AuthenticationException ex) {
        return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(envelope(
                40100, "UNAUTHORIZED", ex.getMessage(), null
        ));
    }

    @ExceptionHandler(AccessDeniedException.class)
    public ResponseEntity<Map<String, Object>> onAccess(AccessDeniedException ex) {
        return ResponseEntity.status(HttpStatus.FORBIDDEN).body(envelope(
                40300, "FORBIDDEN", "access denied", null
        ));
    }

    @ExceptionHandler(Exception.class)
    public ResponseEntity<Map<String, Object>> onUnexpected(Exception ex) {
        log.error("api_unexpected", ex);
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(envelope(
                50000, "INTERNAL_ERROR", "internal server error", null
        ));
    }

    private static Map<String, Object> envelope(int code, String error, String message, Object details) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("code", code);
        body.put("error", error);
        body.put("message", message);
        if (details != null) {
            body.put("details", details);
        }
        return body;
    }
}
