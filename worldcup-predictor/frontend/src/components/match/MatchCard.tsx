import Link from 'next/link';

import { ValueSignalBadge } from '@/components/prediction/ValueSignalBadge';
import { clampProb, formatMatchDate, formatPercent } from '@/lib/utils';
import type { MatchSummary } from '@/types';

interface MatchCardProps {
  match: MatchSummary;
}

/**
 * Single-match card for the home/list view.
 *
 * Shows:
 *   - both team names + competition tag
 *   - kickoff time (or final score for finished matches)
 *   - 1x2 probability bar (always visible — free tier)
 *   - value-signal badge (level=null hides entirely for non-paying users
 *     when the server returned a `topSignalLevel` of null per the tier matrix)
 */
export function MatchCard({ match }: MatchCardProps) {
  const finished = match.status === 'finished';
  return (
    <Link
      href={`/match/${match.matchId}`}
      className="surface-card block rounded-2xl p-4 transition"
    >
      <div className="flex items-center justify-between text-xs text-slate-400">
        <span className="truncate">{match.competition ?? 'WCP'}</span>
        <span className="tabular-nums">{formatMatchDate(match.matchDate)}</span>
      </div>

      <div className="mt-3 flex items-center justify-between gap-4">
        <div className="flex-1 text-right">
          <div className="text-base font-semibold text-slate-100">{match.homeTeam}</div>
        </div>
        <div className="shrink-0 text-center text-sm font-semibold text-slate-300">
          {finished ? <FinalScorePlaceholder /> : <span className="text-brand-400">VS</span>}
        </div>
        <div className="flex-1 text-left">
          <div className="text-base font-semibold text-slate-100">{match.awayTeam}</div>
        </div>
      </div>

      <ProbabilityBar
        home={match.probHomeWin}
        draw={match.probDraw}
        away={match.probAwayWin}
      />

      <div className="mt-3 flex items-center justify-between text-xs">
        <div className="text-slate-400">
          置信{' '}
          <span className="font-semibold tabular-nums text-slate-100">
            {match.confidenceScore ?? '—'}
          </span>
          <span className="text-slate-500">/100</span>
        </div>
        <ValueSignalBadge level={match.topSignalLevel} />
      </div>
    </Link>
  );
}

function FinalScorePlaceholder() {
  return (
    <span className="rounded-md border border-slate-700 bg-slate-800/70 px-2 py-0.5 text-xs uppercase tracking-wider text-slate-400">
      已结束
    </span>
  );
}

function ProbabilityBar({
  home,
  draw,
  away,
}: {
  home: number | null;
  draw: number | null;
  away: number | null;
}) {
  const h = clampProb(home);
  const d = clampProb(draw);
  const a = clampProb(away);
  if (h + d + a === 0) {
    return (
      <div
        className="mt-3 h-7 w-full rounded-full border border-slate-800 bg-slate-900/60"
        aria-label="暂无预测"
      />
    );
  }
  return (
    <div className="mt-3 flex h-7 w-full overflow-hidden rounded-full text-[11px] font-semibold leading-7 ring-1 ring-slate-800/80">
      <div
        className="flex justify-center bg-emerald-500/90 text-emerald-950"
        style={{ width: `${(h * 100).toFixed(1)}%` }}
        title={`主胜 ${formatPercent(h)}`}
      >
        {formatPercent(h)}
      </div>
      <div
        className="flex justify-center bg-amber-400/90 text-amber-950"
        style={{ width: `${(d * 100).toFixed(1)}%` }}
        title={`平局 ${formatPercent(d)}`}
      >
        {formatPercent(d)}
      </div>
      <div
        className="flex justify-center bg-rose-500/90 text-rose-50"
        style={{ width: `${(a * 100).toFixed(1)}%` }}
        title={`客胜 ${formatPercent(a)}`}
      >
        {formatPercent(a)}
      </div>
    </div>
  );
}
