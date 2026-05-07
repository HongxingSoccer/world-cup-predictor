'use client';

import { useT } from '@/i18n/I18nProvider';
import { cn } from '@/lib/utils';
import type { SignalLevel } from '@/types';

interface ValueSignalBadgeProps {
  level: SignalLevel | null | undefined;
  /** When true, hides the badge entirely if level is 0 / null. */
  hideEmpty?: boolean;
}

const STAR_LABEL: Record<NonNullable<Exclude<SignalLevel, 0>>, string> = {
  1: '⭐',
  2: '⭐⭐',
  3: '⭐⭐⭐',
};

const TONE_BY_LEVEL: Record<NonNullable<Exclude<SignalLevel, 0>>, string> = {
  1: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
  2: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  3: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
};

export function ValueSignalBadge({ level, hideEmpty = false }: ValueSignalBadgeProps) {
  const t = useT();
  if (level === null || level === undefined || level === 0) {
    if (hideEmpty) return null;
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-slate-700 bg-slate-800/60 px-2.5 py-0.5 text-xs text-slate-400">
        {t('prediction.noSignal')}
      </span>
    );
  }
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold',
        TONE_BY_LEVEL[level],
      )}
      aria-label={t('prediction.signalLevel').replace('{level}', String(level))}
    >
      {STAR_LABEL[level]}
      <span className="ml-1 text-[10px] uppercase tracking-wider opacity-75">
        {t('prediction.signalLabel')}
      </span>
    </span>
  );
}
