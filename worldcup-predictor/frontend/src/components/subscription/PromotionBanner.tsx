'use client';

import { Sparkles, X } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useState } from 'react';

import { useT } from '@/i18n/I18nProvider';
import { useSubscription } from '@/hooks/useSubscription';

const STORAGE_KEY = 'wcp_promo_dismissed_at';
// Snooze for two weeks after dismissal — long enough to not annoy, short
// enough that returning users see a reminder once a month.
const SNOOZE_MS = 14 * 24 * 3600 * 1000;

/**
 * Bottom-of-page promo for free users. Persistently dismissible: a click
 * on the close button writes a timestamp to localStorage; the banner stays
 * hidden for SNOOZE_MS, then reappears.
 */
export function PromotionBanner() {
  const t = useT();
  const { tier } = useSubscription();
  const [hidden, setHidden] = useState(true); // start hidden until we read storage

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const dismissedAt = raw ? Number.parseInt(raw, 10) : 0;
    setHidden(dismissedAt > 0 && Date.now() - dismissedAt < SNOOZE_MS);
  }, []);

  if (tier !== 'free' || hidden) return null;

  const dismiss = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEY, String(Date.now()));
    }
    setHidden(true);
  };

  return (
    <div className="relative">
      <Link
        href="/subscribe"
        className="block rounded-2xl bg-gradient-to-r from-brand-500 to-accent-500 p-5 text-slate-950 shadow-lg transition hover:shadow-xl"
      >
        <div className="flex items-center gap-3">
          <Sparkles size={22} />
          <div className="flex-1 pr-8">
            <div className="text-base font-bold">{t('subscription.title')}</div>
            <div className="text-sm opacity-90">{t('subscription.promoDescription')}</div>
          </div>
          <span className="hidden rounded-full bg-slate-950/20 px-3 py-1 text-xs font-semibold sm:inline-block">
            {t('subscription.promoCta')}
          </span>
        </div>
      </Link>
      <button
        type="button"
        onClick={dismiss}
        aria-label={t('subscription.closeBanner')}
        className="absolute right-2 top-2 flex h-7 w-7 items-center justify-center rounded-full bg-slate-950/20 text-slate-950 transition hover:bg-slate-950/40"
      >
        <X size={14} />
      </button>
    </div>
  );
}
