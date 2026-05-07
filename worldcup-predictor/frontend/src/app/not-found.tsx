'use client';

import Link from 'next/link';

import { Button } from '@/components/ui/Button';
import { useT } from '@/i18n/I18nProvider';

export default function NotFound() {
  const t = useT();
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center px-4 text-center">
      <div className="hero-number text-7xl font-black sm:text-8xl">404</div>
      <h1 className="mt-3 text-xl font-bold text-slate-100">{t('notFound.title')}</h1>
      <p className="mt-2 max-w-sm text-sm leading-relaxed text-slate-400">{t('notFound.body')}</p>
      <div className="mt-6 flex flex-wrap gap-3">
        <Link href="/">
          <Button>{t('common.backHome')}</Button>
        </Link>
        <Link href="/track-record">
          <Button variant="ghost">{t('notFound.viewTrackRecord')}</Button>
        </Link>
      </div>
    </div>
  );
}
