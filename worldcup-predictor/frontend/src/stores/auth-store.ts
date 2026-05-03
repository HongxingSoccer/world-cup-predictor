/**
 * Zustand auth store — single source of truth for the logged-in user.
 *
 * Persists to localStorage so a hard refresh keeps the session alive (until
 * the access token expires + the refresh interceptor fails). Tokens
 * themselves stay in `lib/auth.ts`'s storage; this store only tracks the
 * user object + boolean flags.
 */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import { apiPost } from '@/lib/api';
import { clearTokens, saveTokens } from '@/lib/auth';
import type { AuthResponse, UserResponse } from '@/types';

interface LoginArgs {
  phone?: string;
  email?: string;
  password: string;
}

interface RegisterArgs extends LoginArgs {
  nickname?: string;
}

interface AuthState {
  user: UserResponse | null;
  isAuthenticated: boolean;

  login: (args: LoginArgs) => Promise<UserResponse>;
  register: (args: RegisterArgs) => Promise<UserResponse>;
  logout: () => Promise<void>;
  setUser: (user: UserResponse | null) => void;
  hydrateFromMe: (user: UserResponse) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,

      login: async (args) => {
        const data = await apiPost<AuthResponse, LoginArgs>('/api/v1/auth/login', args);
        saveTokens(data.accessToken, data.refreshToken);
        set({ user: data.user, isAuthenticated: true });
        return data.user;
      },

      register: async (args) => {
        const data = await apiPost<AuthResponse, RegisterArgs>('/api/v1/auth/register', args);
        saveTokens(data.accessToken, data.refreshToken);
        set({ user: data.user, isAuthenticated: true });
        return data.user;
      },

      logout: async () => {
        try {
          await apiPost('/api/v1/auth/logout');
        } catch {
          // Even if the server-side blacklist call fails we still clear local state.
        }
        clearTokens();
        set({ user: null, isAuthenticated: false });
      },

      setUser: (user) => set({ user, isAuthenticated: user !== null }),

      hydrateFromMe: (user) => set({ user, isAuthenticated: true }),
    }),
    {
      name: 'wcp.auth',
      // Persist only the cached user shape — tokens have their own keyspace.
      partialize: (state) => ({ user: state.user, isAuthenticated: state.isAuthenticated }),
    },
  ),
);
