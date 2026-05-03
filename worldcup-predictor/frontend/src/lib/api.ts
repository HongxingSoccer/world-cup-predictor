/**
 * Axios client targeting the Java business service.
 *
 * - Reads `NEXT_PUBLIC_API_URL` (set in `.env`) for the base URL.
 * - Request interceptor attaches `Authorization: Bearer <access>`.
 * - Response interceptor: on 401, tries the refresh-token endpoint exactly
 *   once and retries the original request. If refresh fails, clears tokens
 *   and (in the browser) redirects to /login.
 */
import axios, {
  AxiosError,
  type AxiosInstance,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from 'axios';

import type { AuthResponse } from '@/types';

import { clearTokens, getAccessToken, getRefreshToken, saveTokens } from './auth';

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8080';

interface RetriableConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

export const api: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15_000,
  headers: { 'Content-Type': 'application/json' },
});

// --- Request interceptor: attach JWT -------------------------------------

api.interceptors.request.use((config) => {
  const token = getAccessToken();
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`);
  }
  return config;
});

// --- Response interceptor: refresh-token retry on 401 --------------------

let refreshInFlight: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refresh = getRefreshToken();
  if (!refresh) {
    return null;
  }
  // Use a bare axios call — bypassing this instance's interceptors avoids
  // an infinite loop if the refresh endpoint itself returns 401.
  try {
    const response = await axios.post<AuthResponse>(
      `${API_BASE_URL}/api/v1/auth/refresh`,
      { refreshToken: refresh },
      { timeout: 10_000 },
    );
    saveTokens(response.data.accessToken, response.data.refreshToken);
    return response.data.accessToken;
  } catch {
    clearTokens();
    return null;
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetriableConfig | undefined;
    if (!original || original._retry || error.response?.status !== 401) {
      return Promise.reject(error);
    }
    original._retry = true;

    refreshInFlight ??= refreshAccessToken();
    const newToken = await refreshInFlight;
    refreshInFlight = null;

    if (!newToken) {
      // Soft redirect — only when running in the browser.
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
        window.location.href = '/login';
      }
      return Promise.reject(error);
    }

    original.headers.set('Authorization', `Bearer ${newToken}`);
    return api(original);
  },
);

// --- SWR fetcher ---------------------------------------------------------

export async function swrFetcher<T = unknown>(url: string): Promise<T> {
  const response = await api.get<T>(url);
  return response.data;
}

// --- Convenience helpers -------------------------------------------------

export async function apiGet<T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T> {
  const response = await api.get<T>(url, config);
  return response.data;
}

export async function apiPost<T = unknown, B = unknown>(
  url: string,
  body?: B,
  config?: AxiosRequestConfig,
): Promise<T> {
  const response = await api.post<T>(url, body, config);
  return response.data;
}
