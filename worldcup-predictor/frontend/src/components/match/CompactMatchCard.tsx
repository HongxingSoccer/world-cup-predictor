import Link from 'next/link';

import { clampProb, formatMatchDate, formatPercent } from '@/lib/utils';

export interface CompactMatch {
  matchId: number;
  matchDate: string;
  homeTeam: string;
  awayTeam: string;
  competition?: string | null;
  status: string;
  round?: string | null;
  homeScore?: number | null;
  awayScore?: number | null;
  probHomeWin?: number | null;
  probDraw?: number | null;
  probAwayWin?: number | null;
  confidenceScore?: number | null;
}

interface Props {
  match: CompactMatch;
}

/**
 * Slim card for "我的收藏" + "同组比赛". Smaller than MatchCard — drops the
 * full probability bar in favour of a single VS vs final-score line so a
 * grid of these stays scannable.
 */
export function CompactMatchCard({ match }: Props) {
  const finished = match.status === 'finished';
  const score =
    finished && match.homeScore !== null && match.homeScore !== undefined
      ? `${match.homeScore} - ${match.awayScore ?? 0}`
      : null;

  const favored = pickFavored(match);
  return (
    <Link
      href={`/match/${match.matchId}`}
      className="surface-card block rounded-xl p-3 transition"
    >
      <div className="flex items-center justify-between text-[11px] text-slate-400">
        <span className="truncate">
          {match.round ?? match.competition ?? 'WCP'}
        </span>
        <span className="tabular-nums">{formatMatchDate(match.matchDate)}</span>
      </div>

      <div className="mt-2 flex items-center justify-between gap-3">
        <div className="flex-1 truncate text-sm font-semibold text-slate-100">
          {match.homeTeam}
        </div>
        <div className="shrink-0 text-xs font-semibold tabular-nums">
          {score ? (
            <span className="text-slate-100">{score}</span>
          ) : (
            <span className="text-brand-400">VS</span>
          )}
        </div>
        <div className="flex-1 truncate text-right text-sm font-semibold text-slate-100">
          {match.awayTeam}
        </div>
      </div>

      {favored && !finished ? (
        <div className="mt-2 text-[11px] text-slate-400">
          模型偏向{' '}
          <span className="font-semibold text-cyan-300">{favored.label}</span>
          <span className="ml-1 tabular-nums text-slate-300">
            {formatPercent(clampProb(favored.prob))}
          </span>
        </div>
      ) : null}
    </Link>
  );
}

function pickFavored(m: CompactMatch): { label: string; prob: number } | null {
  const home = m.probHomeWin ?? null;
  const draw = m.probDraw ?? null;
  const away = m.probAwayWin ?? null;
  if (home === null || draw === null || away === null) return null;
  if (home >= draw && home >= away) return { label: m.homeTeam, prob: home };
  if (away >= draw && away >= home) return { label: m.awayTeam, prob: away };
  return { label: '平局', prob: draw };
}
