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
      className="block rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition hover:border-slate-300 hover:shadow-md"
    >
      <div className="flex items-center justify-between text-xs text-slate-500">
        <span className="truncate">{match.competition ?? 'WCP'}</span>
        <span>{formatMatchDate(match.matchDate)}</span>
      </div>

      <div className="mt-3 flex items-center justify-between gap-4">
        <div className="flex-1 text-right">
          <div className="text-base font-semibold text-slate-900">{match.homeTeam}</div>
        </div>
        <div className="shrink-0 text-center text-sm font-semibold text-slate-700">
          {finished ? <FinalScorePlaceholder /> : 'VS'}
        </div>
        <div className="flex-1 text-left">
          <div className="text-base font-semibold text-slate-900">{match.awayTeam}</div>
        </div>
      </div>

      <ProbabilityBar
        home={match.probHomeWin}
        draw={match.probDraw}
        away={match.probAwayWin}
      />

      <div className="mt-3 flex items-center justify-between text-xs">
        <div className="text-slate-500">
          置信 <span className="font-semibold text-slate-800">{match.confidenceScore ?? '—'}</span>
          /100
        </div>
        <ValueSignalBadge level={match.topSignalLevel} />
      </div>
    </Link>
  );
}

function FinalScorePlaceholder() {
  // Final-score isn't carried by the matches/today response in the current
  // backend contract — we surface a neutral pill rather than fabricating
  // numbers. The match-detail view shows the real score.
  return (
    <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs uppercase tracking-wider text-slate-500">
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
      <div className="mt-3 h-7 w-full rounded-full bg-slate-100" aria-label="暂无预测" />
    );
  }
  return (
    <div className="mt-3 flex h-7 w-full overflow-hidden rounded-full text-[11px] font-semibold leading-7 text-white">
      <div
        className="flex justify-center bg-emerald-500"
        style={{ width: `${(h * 100).toFixed(1)}%` }}
        title={`主胜 ${formatPercent(h)}`}
      >
        {formatPercent(h)}
      </div>
      <div
        className="flex justify-center bg-amber-400 text-amber-950"
        style={{ width: `${(d * 100).toFixed(1)}%` }}
        title={`平局 ${formatPercent(d)}`}
      >
        {formatPercent(d)}
      </div>
      <div
        className="flex justify-center bg-rose-500"
        style={{ width: `${(a * 100).toFixed(1)}%` }}
        title={`客胜 ${formatPercent(a)}`}
      >
        {formatPercent(a)}
      </div>
    </div>
  );
}
