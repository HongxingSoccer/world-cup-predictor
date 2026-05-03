import type { SignalLevel } from '@/types';
import { cn } from '@/lib/utils';

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
  1: 'bg-sky-100 text-sky-800 border-sky-200',
  2: 'bg-amber-100 text-amber-800 border-amber-200',
  3: 'bg-emerald-100 text-emerald-800 border-emerald-200',
};

export function ValueSignalBadge({ level, hideEmpty = false }: ValueSignalBadgeProps) {
  if (level === null || level === undefined || level === 0) {
    if (hideEmpty) return null;
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 text-xs text-slate-500">
        无信号
      </span>
    );
  }
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold',
        TONE_BY_LEVEL[level],
      )}
      aria-label={`价值信号 ${level} 级`}
    >
      {STAR_LABEL[level]}
      <span className="ml-1 text-[10px] uppercase tracking-wider opacity-75">价值</span>
    </span>
  );
}
