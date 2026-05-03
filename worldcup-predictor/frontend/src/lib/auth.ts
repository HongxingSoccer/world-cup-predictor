/**
 * Browser-side JWT storage helpers.
 *
 * We store both tokens in `localStorage` for now — Phase 4 will move the
 * refresh token to an HttpOnly cookie. The access token has to be readable
 * from JS so the axios interceptor can attach it.
 */

const ACCESS_KEY = 'wcp.access_token';
const REFRESH_KEY = 'wcp.refresh_token';

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
}

export function clearTokens(): void {
  if (!isBrowser()) return;
  window.localStorage.removeItem(ACCESS_KEY);
  window.localStorage.removeItem(REFRESH_KEY);
}
