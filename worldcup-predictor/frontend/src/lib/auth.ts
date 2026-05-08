/**
 * Browser-side JWT storage helpers.
 *
 * Tokens live in `localStorage` so the axios interceptor can attach them.
 * The access token is *also* mirrored to a same-site cookie (`ACCESS_COOKIE`)
 * so Next.js server components can read it via `cookies()` and forward it
 * upstream — without that, SSR fetches go out anonymous and tier-gated
 * fields (score matrix, odds analysis, etc.) come back null even for paying
 * users. Phase 4 will swap this for an HttpOnly refresh-token cookie.
 */

const ACCESS_KEY = 'wcp.access_token';
const REFRESH_KEY = 'wcp.refresh_token';
export const ACCESS_COOKIE = 'wcp_access';
const ACCESS_COOKIE_MAX_AGE = 60 * 60 * 2; // mirror the JWT's 2h TTL

/** Server-rendering safe — `localStorage` only exists in the browser. */
const isBrowser = (): boolean => typeof window !== 'undefined';

export function getAccessToken(): string | null {
  if (!isBrowser()) return null;
  return window.localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  if (!isBrowser()) return null;
  return window.localStorage.getItem(REFRESH_KEY);
}

export function saveTokens(access: string, refresh: string): void {
  if (!isBrowser()) return;
  window.localStorage.setItem(ACCESS_KEY, access);
  window.localStorage.setItem(REFRESH_KEY, refresh);
  document.cookie = `${ACCESS_COOKIE}=${encodeURIComponent(access)}; path=/; max-age=${ACCESS_COOKIE_MAX_AGE}; samesite=lax`;
}

export function clearTokens(): void {
  if (!isBrowser()) return;
  window.localStorage.removeItem(ACCESS_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
  document.cookie = `${ACCESS_COOKIE}=; path=/; max-age=0`;
}
