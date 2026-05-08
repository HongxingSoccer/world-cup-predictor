/**
 * Lightweight client-side i18n provider.
 *
 * Locale resolution: explicit `initialLocale` prop (set by the server-side
 * layout from the `locale` cookie) → cookie read on the client → navigator
 * preference → default zh-CN. The server-side seeding eliminates the
 * server/client hydration mismatch that broke instant locale switching.
 */
'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import enMessages from '@/i18n/en.json';
import zhMessages from '@/i18n/zh-CN.json';

// Constants live in `./config` so the server layout can import them by
// value (a `'use client'` file's exports become reference proxies on the
// server). Re-exported here for ergonomic backwards-compatible imports.
export {
  DEFAULT_LOCALE,
  LOCALE_COOKIE,
  SUPPORTED_LOCALES,
  type Locale,
} from '@/i18n/config';
import { DEFAULT_LOCALE, LOCALE_COOKIE, type Locale, SUPPORTED_LOCALES } from '@/i18n/config';

const MESSAGES: Record<Locale, Record<string, unknown>> = {
  'zh-CN': zhMessages as Record<string, unknown>,
  en: enMessages as Record<string, unknown>,
};

type Ctx = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: string, fallback?: string) => string;
};

const I18nContext = createContext<Ctx | null>(null);

function readCookieLocale(): Locale | null {
  if (typeof document === 'undefined') return null;
  const m = document.cookie.match(/(?:^|; )locale=([^;]+)/);
  if (!m) return null;
  const v = decodeURIComponent(m[1]) as Locale;
  return SUPPORTED_LOCALES.includes(v) ? v : null;
}

function detectClientLocale(): Locale {
  const fromCookie = readCookieLocale();
  if (fromCookie) return fromCookie;
  if (typeof navigator !== 'undefined') {
    const lang = navigator.language?.toLowerCase() ?? '';
    if (lang.startsWith('en')) return 'en';
  }
  return DEFAULT_LOCALE;
}

function lookup(messages: Record<string, unknown>, key: string): string | null {
  const parts = key.split('.');
  let node: unknown = messages;
  for (const p of parts) {
    if (node && typeof node === 'object' && p in (node as Record<string, unknown>)) {
      node = (node as Record<string, unknown>)[p];
    } else {
      return null;
    }
  }
  return typeof node === 'string' ? node : null;
}

interface Props {
  children: React.ReactNode;
  /** Server-resolved locale, used for the initial render so SSR + CSR match. */
  initialLocale?: Locale;
}

export function I18nProvider({ children, initialLocale }: Props) {
  const [locale, setLocaleState] = useState<Locale>(initialLocale ?? DEFAULT_LOCALE);
  const seeded = useRef(Boolean(initialLocale));

  // If the server didn't seed (e.g. older layout), reconcile from cookie /
  // navigator after mount. When the server DID seed, we trust it and skip
  // this — avoids overriding a freshly-clicked locale on hot reload.
  useEffect(() => {
    if (seeded.current) return;
    setLocaleState(detectClientLocale());
  }, []);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    if (typeof document !== 'undefined') {
      document.cookie = `${LOCALE_COOKIE}=${encodeURIComponent(next)}; path=/; max-age=${60 * 60 * 24 * 365}`;
      document.documentElement.lang = next;
    }
  }, []);

  const t = useCallback(
    (key: string, fallback?: string) => {
      const value = lookup(MESSAGES[locale], key);
      if (value !== null) return value;
      const fb = lookup(MESSAGES[DEFAULT_LOCALE], key);
      return fb ?? fallback ?? key;
    },
    [locale],
  );

  const value = useMemo<Ctx>(() => ({ locale, setLocale, t }), [locale, setLocale, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): Ctx {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    return {
      locale: DEFAULT_LOCALE,
      setLocale: () => undefined,
      t: (k, f) => lookup(MESSAGES[DEFAULT_LOCALE], k) ?? f ?? k,
    };
  }
  return ctx;
}

export function useT() {
  return useI18n().t;
}
