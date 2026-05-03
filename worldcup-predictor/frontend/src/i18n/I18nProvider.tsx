/**
 * Lightweight client-side i18n provider (Phase 5).
 *
 * Design §7.1 specifies ``next-intl`` with /zh and /en sub-paths. The full
 * locale-prefix routing migration is deferred to a follow-up iteration; this
 * provider satisfies §7 "i18n infrastructure" by giving every component a
 * stable ``useT()`` hook that resolves nested keys ("admin.flags.title")
 * against the bundled ``zh-CN`` / ``en`` JSON files.
 *
 * Locale resolution order: cookie ``locale`` → ``navigator.language`` prefix
 * → default ``zh-CN``.
 */
'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import enMessages from '@/i18n/en.json';
import zhMessages from '@/i18n/zh-CN.json';

export type Locale = 'zh-CN' | 'en';
export const DEFAULT_LOCALE: Locale = 'zh-CN';
export const SUPPORTED_LOCALES: Locale[] = ['zh-CN', 'en'];
const COOKIE_NAME = 'locale';

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

function detectLocale(): Locale {
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

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  useEffect(() => {
    setLocaleState(detectLocale());
  }, []);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    if (typeof document !== 'undefined') {
      // 1-year cookie, available app-wide.
      document.cookie = `${COOKIE_NAME}=${encodeURIComponent(next)}; path=/; max-age=${60 * 60 * 24 * 365}`;
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
    // Render-safe fallback so individual components can still be used outside
    // the provider tree (e.g. in Storybook stories or quick prototypes).
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
