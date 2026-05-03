package com.wcp.model.enums;

/**
 * Access tier for content gating.
 *
 * <p>Persisted as a lowercase VARCHAR string ({@code free} / {@code basic} /
 * {@code premium}) to match the Python schema; never use {@link Enum#name()}
 * directly when serialising — use {@link #wireValue()}.
 */
public enum SubscriptionTier {
    FREE("free"),
    BASIC("basic"),
    PREMIUM("premium");

    private final String wire;

    SubscriptionTier(String wire) {
        this.wire = wire;
    }

    public String wireValue() {
        return wire;
    }

    public static SubscriptionTier fromWire(String value) {
        if (value == null) {
            return FREE;
        }
        return switch (value) {
            case "basic" -> BASIC;
            case "premium" -> PREMIUM;
            default -> FREE;
        };
    }

    /** True when this tier provides at least the given minimum access level. */
    public boolean isAtLeast(SubscriptionTier min) {
        return this.ordinal() >= min.ordinal();
    }
}
