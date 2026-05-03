/**
 * Convenience hook bundling the auth store + a one-time `me()` rehydration
 * effect on mount. Components that need the user import this rather than
 * the raw store.
 */
'use client';

import { useEffect } from 'react';

import { apiGet } from '@/lib/api';
import { getAccessToken } from '@/lib/auth';
import { useAuthStore } from '@/stores/auth-store';
import { useSubscriptionStore } from '@/stores/subscription-store';
import type { UserResponse } from '@/types';

interface UseAuthResult {
  user: UserResponse | null;
  isAuthenticated: boolean;
  isLoadingMe: boolean;
}

export function useAuth(): UseAuthResult {
  const { user, isAuthenticated, hydrateFromMe } = useAuthStore();
  const setTier = useSubscriptionStore((s) => s.setTier);

  useEffect(() => {
    // If we have a token but no cached user, hydrate via /me.
    const token = getAccessToken();
    if (!token || isAuthenticated) {
      return;
    }
    let cancelled = false;
    apiGet<UserResponse>('/api/v1/users/me')
      .then((u) => {
        if (cancelled) return;
        hydrateFromMe(u);
        setTier(u.subscriptionTier, u.subscriptionExpires ?? null);
      })
      .catch(() => {
        // Token expired / invalid — the API client redirects to /login on the
        // 401 path; nothing to do here.
      });
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, hydrateFromMe, setTier]);

  // Keep subscription store in sync with the latest user payload.
  useEffect(() => {
    if (user) {
      setTier(user.subscriptionTier, user.subscriptionExpires ?? null);
    }
  }, [user, setTier]);

  return {
    user,
    isAuthenticated,
    isLoadingMe: false,
  };
}
