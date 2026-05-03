package com.wcp.security;

import com.wcp.model.User;
import com.wcp.model.enums.SubscriptionTier;
import java.util.List;
import java.util.UUID;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.UserDetails;

/**
 * Spring-Security principal carrying the project-specific user attributes.
 *
 * <p>Stored on {@code SecurityContextHolder} after JWT validation so any
 * downstream {@code @AuthenticationPrincipal UserPrincipal} controller arg
 * gets the user's UUID, role, and subscription tier without re-querying.
 */
public record UserPrincipal(
        Long id,
        UUID uuid,
        String role,
        SubscriptionTier subscriptionTier,
        boolean active
) implements UserDetails {

    public static UserPrincipal from(User user) {
        return new UserPrincipal(
                user.getId(),
                user.getUuid(),
                user.getRole(),
                SubscriptionTier.fromWire(user.getSubscriptionTier()),
                user.isActive()
        );
    }

    public static UserPrincipal anonymous() {
        return new UserPrincipal(null, null, "anonymous", SubscriptionTier.FREE, true);
    }

    @Override
    public List<? extends GrantedAuthority> getAuthorities() {
        return List.of(new SimpleGrantedAuthority("ROLE_" + role.toUpperCase()));
    }

    @Override
    public String getPassword() {
        return ""; // Not used for JWT auth.
    }

    @Override
    public String getUsername() {
        return uuid != null ? uuid.toString() : "anonymous";
    }

    @Override
    public boolean isAccountNonExpired() {
        return active;
    }

    @Override
    public boolean isAccountNonLocked() {
        return active;
    }

    @Override
    public boolean isCredentialsNonExpired() {
        return true;
    }

    @Override
    public boolean isEnabled() {
        return active;
    }
}
