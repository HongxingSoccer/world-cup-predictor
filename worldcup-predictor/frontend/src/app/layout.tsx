import type { Metadata, Viewport } from 'next';

import { Footer } from '@/components/layout/Footer';
import { Header } from '@/components/layout/Header';
import { MobileNav } from '@/components/layout/MobileNav';
import { I18nProvider } from '@/i18n/I18nProvider';

import './globals.css';

export const metadata: Metadata = {
  title: {
    default: 'WCP · 世界杯预测',
    template: '%s | WCP · 世界杯预测',
  },
  description: '基于 AI 模型的 2026 世界杯预测与赔率价值分析。',
  // 中文 + 英文 OG
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

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700;900&display=swap"
        />
      </head>
      <body className="font-sans">
        <I18nProvider>
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
