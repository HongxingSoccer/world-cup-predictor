import type { Metadata, Viewport } from 'next';
import { cookies } from 'next/headers';

import { Footer } from '@/components/layout/Footer';
import { Header } from '@/components/layout/Header';
import { MobileNav } from '@/components/layout/MobileNav';
// IMPORTANT: pull constants from `@/i18n/config` (server-safe), not from
// `I18nProvider.tsx` (which is `'use client'`). Re-exported constants
// from a client component become runtime reference proxies on the server,
// which silently broke `cookies().get(LOCALE_COOKIE)` and pinned every
// SSR request to the default locale.
import {
  DEFAULT_LOCALE,
  LOCALE_COOKIE,
  SUPPORTED_LOCALES,
  type Locale,
} from '@/i18n/config';
import { I18nProvider } from '@/i18n/I18nProvider';

import './globals.css';

export const metadata: Metadata = {
  title: {
    default: 'WCP · 世界杯预测',
    template: '%s | WCP · 世界杯预测',
  },
  description: '基于 AI 模型的 2026 世界杯预测与赔率价值分析。',
  openGraph: {
    siteName: 'WCP · 世界杯预测',
    type: 'website',
    locale: 'zh_CN',
  },
  twitter: { card: 'summary_large_image' },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: '#0a0e1a',
};

// The root layout reads the `locale` cookie per request to pick the
// initial locale. Without `force-dynamic` Next can still pre-render
// downstream pages and bake the wrong language into the static HTML.
export const dynamic = 'force-dynamic';

// Reading cookies in the root layout opts every page under it out of
// static rendering. That's intentional — the locale cookie has to be
// read per-request, otherwise the whole site bakes to one language at
// build time. The try/catch from the first attempt was masking Next's
// "this route is now dynamic" signal, so static rendering kept winning
// and the cookie was never read.
function resolveServerLocale(): Locale {
  const v = cookies().get(LOCALE_COOKIE)?.value;
  if (v && (SUPPORTED_LOCALES as readonly string[]).includes(v)) {
    return v as Locale;
  }
  return DEFAULT_LOCALE;
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const locale = resolveServerLocale();
  const htmlLang = locale === 'en' ? 'en' : 'zh-CN';
  return (
    <html lang={htmlLang}>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700;900&display=swap"
        />
      </head>
      <body className="font-sans">
        <I18nProvider initialLocale={locale}>
          <Header />
          <main className="mx-auto max-w-6xl px-4 pb-24 pt-4 md:pb-8 md:pt-6">
            {children}
          </main>
          <Footer />
          <MobileNav />
        </I18nProvider>
      </body>
    </html>
  );
}
