'use client';

import { Languages } from 'lucide-react';

import { useI18n, type Locale } from '@/i18n/I18nProvider';

/**
 * One-click locale switcher for the header. Cycles between zh-CN and en
 * (the only two locales we ship). Designed to fit between the nav links
 * and the profile pill — keeps the header dense.
 */
export function CompactLocaleToggle() {
  const { locale, setLocale } = useI18n();
  const next: Locale = locale === 'zh-CN' ? 'en' : 'zh-CN';
  const label = locale === 'zh-CN' ? 'EN' : '中';
  return (
    <button
      type="button"
      onClick={() => setLocale(next)}
      className="hidden h-9 items-center gap-1.5 rounded-full border border-slate-700 bg-slate-800/70 px-3 text-xs font-semibold tabular-nums text-slate-300 transition-colors hover:border-brand-500/40 hover:text-brand-400 sm:inline-flex"
      aria-label={`Switch to ${next}`}
    >
      <Languages size={14} />
      {label}
    </button>
  );
}
