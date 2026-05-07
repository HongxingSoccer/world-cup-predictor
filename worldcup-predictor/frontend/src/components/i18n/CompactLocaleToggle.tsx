'use client';

import { Languages } from 'lucide-react';
import { useRouter } from 'next/navigation';

import { useI18n, type Locale } from '@/i18n/I18nProvider';

/**
 * One-click locale switcher for the header. Cycles between zh-CN and en
 * (the only two locales we ship). After flipping client state we also
 * call router.refresh() so any server-rendered text (page metadata,
 * server-component bodies, ISR'd HTML) re-renders with the new cookie.
 */
export function CompactLocaleToggle() {
  const { locale, setLocale } = useI18n();
  const router = useRouter();
  const next: Locale = locale === 'zh-CN' ? 'en' : 'zh-CN';
  const label = locale === 'zh-CN' ? 'EN' : '中';

  const onClick = () => {
    setLocale(next);
    // Re-fetch RSC payload so SSR'd text follows the new cookie.
    router.refresh();
  };

  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex h-9 items-center gap-1.5 rounded-full border border-slate-700 bg-slate-800/70 px-3 text-xs font-semibold tabular-nums text-slate-300 transition-colors hover:border-brand-500/40 hover:text-brand-400"
      aria-label={`Switch to ${next}`}
    >
      <Languages size={14} />
      {label}
    </button>
  );
}
