'use client';

import { SUPPORTED_LOCALES, useI18n, type Locale } from '@/i18n/I18nProvider';

const LABELS: Record<Locale, string> = {
  'zh-CN': '中文',
  en: 'English',
};

export function LocaleSwitcher({ className = '' }: { className?: string }) {
  const { locale, setLocale, t } = useI18n();
  return (
    <label className={`inline-flex items-center gap-2 text-sm text-slate-400 ${className}`}>
      <span>{t('admin.locale.label', 'Language')}</span>
      <select
        value={locale}
        onChange={(e) => setLocale(e.target.value as Locale)}
        className="rounded-md border border-slate-700 bg-slate-900/70 px-2 py-1"
        aria-label="locale-switcher"
      >
        {SUPPORTED_LOCALES.map((l) => (
          <option key={l} value={l}>
            {LABELS[l]}
          </option>
        ))}
      </select>
    </label>
  );
}
