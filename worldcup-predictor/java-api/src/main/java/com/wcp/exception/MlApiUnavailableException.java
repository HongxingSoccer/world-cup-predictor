package com.wcp.exception;

import org.springframework.http.HttpStatus;

/**
 * Raised when ml-api is unreachable or returns a 5xx for an upstream call
 * whose contract is "must succeed for the user-facing operation to mean
 * anything" (e.g. hedge calculations — without ml-api there's no math).
 *
 * <p>Differs from most existing ml-api consumers, which degrade gracefully
 * by returning empty maps. Mapped to HTTP 503.
 */
public class MlApiUnavailableException extends ApiException {

    public MlApiUnavailableException(String detail) {
        super(
                HttpStatus.SERVICE_UNAVAILABLE,
                50302,
                "ML_API_UNAVAILABLE",
                "upstream ML service is unavailable: " + detail
        );
    }
}
