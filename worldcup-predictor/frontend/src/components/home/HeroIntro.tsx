'use client';

import { Sparkles, TrendingUp, Zap } from 'lucide-react';
import { useEffect, useState } from 'react';

import { useT } from '@/i18n/I18nProvider';
import { useAuth } from '@/hooks/useAuth';

const STORAGE_KEY = 'wcp_hero_dismissed_at';
// Once a user has acknowledged the intro it stays hidden for 30 days. They
// can still find the value-prop on /about; the goal here is anti-clutter,
// not anti-discovery.
const SNOOZE_MS = 30 * 24 * 3600 * 1000;

/**
 * First-impression card for anonymous visitors. Explains the three core
 * value props (AI-driven 1x2, EV signal, transparent track record) and
 * doubles as a soft sign-up nudge. Hides itself for authenticated users
 * and after a 30-day snooze when explicitly dismissed.
 */
export function HeroIntro() {
  const t = useT();
  const { isAuthenticated } = useAuth();
  const [hidden, setHidden] = useState(true);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const dismissedAt = raw ? Number.parseInt(raw, 10) : 0;
    setHidden(dismissedAt > 0 && Date.now() - dismissedAt < SNOOZE_MS);
  }, []);

  if (isAuthenticated || hidden) return null;

  const dismiss = () => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEY, String(Date.now()));
    }
    setHidden(true);
  };

  return (
    <div className="surface-card relative overflow-hidden rounded-2xl p-5 sm:p-6">
      {/* Decorative gradient blob — purely cosmetic */}
      <div
        aria-hidden
        className="pointer-events-none absolute -right-16 -top-12 h-44 w-44 rounded-full bg-gradient-to-br from-cyan-500/30 via-cyan-500/0 to-amber-500/20 blur-2xl"
      />
      <div className="relative">
        <span className="inline-flex items-center gap-1 rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wider text-cyan-300">
          {t('home.heroBadge')}
        </span>
        <h1 className="mt-3 text-xl font-bold text-slate-100 sm:text-2xl">
          {t('home.heroTitleA')} <span className="hero-number">{t('home.heroTitleProb')}</span>{' '}
          {t('home.heroTitleAnd')} <span className="hero-number">{t('home.heroTitleSignal')}</span>
        </h1>
        <p className="mt-2 max-w-lg text-sm leading-relaxed text-slate-300">
          {t('home.heroBodyPrefix')}
          <a href="/track-record" className="text-cyan-300 underline-offset-4 hover:underline">
            {t('home.heroBodyLink')}
          </a>
          {t('home.heroBodySuffix')}
        </p>

        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <Feature
            icon={<TrendingUp size={16} className="text-cyan-300" />}
            title={t('home.feature1Title')}
            detail={t('home.feature1Detail')}
          />
          <Feature
            icon={<Zap size={16} className="text-amber-300" />}
            title={t('home.feature2Title')}
            detail={t('home.feature2Detail')}
          />
          <Feature
            icon={<Sparkles size={16} className="text-emerald-300" />}
            title={t('home.feature3Title')}
            detail={t('home.feature3Detail')}
          />
        </div>

        <div className="mt-5 flex flex-wrap items-center gap-3">
          <a
            href="/login"
            className="inline-flex items-center justify-center rounded-xl bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 shadow-[0_8px_24px_-12px_rgba(34,211,238,0.6)] transition hover:bg-cyan-400"
          >
            {t('home.ctaLogin')}
          </a>
          <a href="/about" className="text-sm text-slate-400 hover:text-cyan-300">
            {t('home.ctaAbout')}
          </a>
          <button
            type="button"
            onClick={dismiss}
            className="ml-auto text-xs text-slate-500 hover:text-slate-300"
          >
            {t('home.dismiss')}
          </button>
        </div>
      </div>
    </div>
  );
}

function Feature({
  icon,
  title,
  detail,
}: {
  icon: React.ReactNode;
  title: string;
  detail: string;
}) {
  return (
    <div className="rounded-xl border border-slate-800/70 bg-slate-900/40 p-3">
      <div className="flex items-center gap-2">
        {icon}
        <span className="text-sm font-semibold text-slate-100">{title}</span>
      </div>
      <p className="mt-1 text-xs leading-relaxed text-slate-400">{detail}</p>
    </div>
  );
}
