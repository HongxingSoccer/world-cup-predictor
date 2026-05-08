// Server-safe locale constants. These have to live OUTSIDE I18nProvider.tsx
// because that file is `'use client'`, and Next.js wraps every export of a
// client component in a runtime reference proxy. When the root layout (a
// server component) imports a constant from a `'use client'` file, it gets
// the proxy — not the underlying string — which silently breaks
// `cookies().get(LOCALE_COOKIE)` (the proxy is not a valid cookie name).
//
// Anything the server needs to *read by value* must come from this file.

export type Locale = 'zh-CN' | 'en';

export const DEFAULT_LOCALE: Locale = 'zh-CN';
export const SUPPORTED_LOCALES: Locale[] = ['zh-CN', 'en'];
export const LOCALE_COOKIE = 'locale';
