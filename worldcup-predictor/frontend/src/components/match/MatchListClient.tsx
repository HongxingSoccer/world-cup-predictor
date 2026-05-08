'use client';

import { Flame, Lock, Star } from 'lucide-react';
import Link from 'next/link';
import { useMemo, useState } from 'react';

import { CompetitionFilter } from './CompetitionFilter';
import { MatchCard } from './MatchCard';
import { useSubscription } from '@/hooks/useSubscription';
import { useT } from '@/i18n/I18nProvider';
import { cn } from '@/lib/utils';
import type { MatchSummary } from '@/types';

interface MatchListClientProps {
  matches: MatchSummary[];
}

type Quality = 'all' | 'high_signal' | 'high_confidence';

const HIGH_CONFIDENCE_THRESHOLD = 70;

/**
 * Client island: SSR-rendered match list + a filter row (competition pills
 * + quality chips). Quality chips only render when the source list is large
 * enough that filtering pays for itself — for ≤6 matches every card already
 * fits on screen so chips are noise.
 */
export function MatchListClient({ matches }: MatchListClientProps) {
  const t = useT();
  const { canAccess } = useSubscription();
  const canFilterByConfidence = canAccess('confidence_filter');
  const [competition, setCompetition] = useState<string | null>(null);
  const [quality, setQuality] = useState<Quality>('all');

  const competitions = useMemo(
    () =>
      Array.from(
        new Set(matches.map((m) => m.competition).filter(Boolean) as string[]),
      ).sort(),
    [matches],
  );

  const showQualityChips = matches.length > 6;
  const counts = useMemo(() => qualityCounts(matches), [matches]);

  const visible = useMemo(() => {
    let out = matches;
    if (competition) out = out.filter((m) => m.competition === competition);
    if (quality === 'high_signal') {
      out = out.filter((m) => (m.topSignalLevel ?? 0) >= 2);
    } else if (quality === 'high_confidence' && canFilterByConfidence) {
      out = out.filter(
        (m) => (m.confidenceScore ?? 0) >= HIGH_CONFIDENCE_THRESHOLD,
      );
    }
    return out;
  }, [matches, competition, quality, canFilterByConfidence]);

  return (
    <div className="space-y-3">
      {showQualityChips ? (
        <QualityChips
          value={quality}
          onChange={setQuality}
          totals={counts}
          allLabel={t('match.filterAll')}
          highEvLabel={t('match.highEVSignal')}
          highConfidenceLabel={t('match.highConfidence')}
          confidenceLocked={!canFilterByConfidence}
        />
      ) : null}
      <CompetitionFilter
        options={competitions}
        value={competition}
        onChange={setCompetition}
      />
      {visible.length === 0 ? (
        <div className="rounded-2xl border border-slate-800/70 bg-slate-900/40 p-6 text-center text-sm text-slate-400">
          {t('match.noFilterResults')}
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {visible.map((match) => (
            <MatchCard key={match.matchId} match={match} />
          ))}
        </div>
      )}
    </div>
  );
}

interface ChipsProps {
  value: Quality;
  onChange: (v: Quality) => void;
  totals: { highSignal: number; highConfidence: number };
  allLabel: string;
  highEvLabel: string;
  highConfidenceLabel: string;
  /** True for free / basic users — chip renders as a CTA to /subscribe. */
  confidenceLocked: boolean;
}

function QualityChips({
  value,
  onChange,
  totals,
  allLabel,
  highEvLabel,
  highConfidenceLabel,
  confidenceLocked,
}: ChipsProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Chip active={value === 'all'} onClick={() => onChange('all')}>
        {allLabel}
      </Chip>
      <Chip
        active={value === 'high_signal'}
        onClick={() => onChange('high_signal')}
        icon={<Flame size={12} className="text-amber-300" />}
        count={totals.highSignal}
      >
        {highEvLabel}
      </Chip>
      {confidenceLocked ? (
        // Lock affordance: tap goes straight to subscribe instead of toggling.
        // We deliberately do NOT change the visible count so users see the
        // value of upgrading.
        <Link href="/subscribe" className="inline-flex">
          <Chip
            active={false}
            onClick={() => undefined}
            icon={<Lock size={11} className="text-slate-500" />}
            count={totals.highConfidence}
            muted
          >
            {highConfidenceLabel}
          </Chip>
        </Link>
      ) : (
        <Chip
          active={value === 'high_confidence'}
          onClick={() => onChange('high_confidence')}
          icon={<Star size={12} className="text-cyan-300" />}
          count={totals.highConfidence}
        >
          {highConfidenceLabel}
        </Chip>
      )}
    </div>
  );
}

function Chip({
  active,
  onClick,
  icon,
  count,
  muted = false,
  children,
}: {
  active: boolean;
  onClick: () => void;
  icon?: React.ReactNode;
  count?: number;
  /** Locked / paywall-pending — renders dimmer than a normal inactive chip. */
  muted?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors',
        active
          ? 'border-cyan-500/40 bg-cyan-500/15 text-cyan-200'
          : muted
            ? 'border-slate-800 bg-slate-900/40 text-slate-500 hover:border-slate-700 hover:text-slate-300'
            : 'border-slate-700 bg-slate-800/60 text-slate-400 hover:border-slate-600 hover:text-slate-200',
      )}
    >
      {icon}
      <span>{children}</span>
      {count !== undefined ? (
        <span
          className={cn(
            'tabular-nums',
            active ? 'text-cyan-200' : 'text-slate-500',
          )}
        >
          ({count})
        </span>
      ) : null}
    </button>
  );
}

function qualityCounts(matches: MatchSummary[]): {
  highSignal: number;
  highConfidence: number;
} {
  let highSignal = 0;
  let highConfidence = 0;
  for (const m of matches) {
    if ((m.topSignalLevel ?? 0) >= 2) highSignal += 1;
    if ((m.confidenceScore ?? 0) >= HIGH_CONFIDENCE_THRESHOLD) highConfidence += 1;
  }
  return { highSignal, highConfidence };
}
