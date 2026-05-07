'use client';

import Link from 'next/link';

import { useT } from '@/i18n/I18nProvider';

export function Footer() {
  const t = useT();
  return (
    <footer className="mt-12 border-t border-slate-800/70 bg-ink-900/40 text-sm text-slate-400 backdrop-blur-sm">
      <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-6 md:flex-row md:items-center md:justify-between">
        <div className="text-slate-500">© {new Date().getFullYear()} {t('brand')}</div>
        <nav className="flex gap-4">
          <Link href="/about" className="transition-colors hover:text-brand-400">
            {t('nav.about')}
          </Link>
          <Link href="/terms" className="transition-colors hover:text-brand-400">
            {t('nav.terms')}
          </Link>
          <Link href="/privacy" className="transition-colors hover:text-brand-400">
            {t('nav.privacy')}
          </Link>
        </nav>
      </div>
    </footer>
  );
}
