import type { Metadata, Viewport } from 'next';
import { cookies } from 'next/headers';

import { Footer } from '@/components/layout/Footer';
import { Header } from '@/components/layout/Header';
import { MobileNav } from '@/components/layout/MobileNav';
import {
  DEFAULT_LOCALE,
  I18nProvider,
  LOCALE_COOKIE,
  SUPPORTED_LOCALES,
  type Locale,
} from '@/i18n/I18nProvider';

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

function resolveServerLocale(): Locale {
  // Server-side cookie read so the SSR pass renders in the same locale the
  // client will hydrate to. Without this the page flashes zh-CN until the
  // client effect reads the cookie + flips state, and any fully-server-
  // rendered text (metadata, server-component bodies) never picks up the
  // locale at all.
  try {
    const v = cookies().get(LOCALE_COOKIE)?.value;
    if (v && (SUPPORTED_LOCALES as readonly string[]).includes(v)) {
      return v as Locale;
    }
  } catch {
    // cookies() throws when called outside a request scope (during the
    // root layout build for static fallbacks). Fall through to default.
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
