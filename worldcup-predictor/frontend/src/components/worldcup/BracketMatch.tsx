import Link from 'next/link';

import { cn, formatPercent } from '@/lib/utils';

export interface BracketMatchData {
  matchId: number | null;
  homeTeam: string | null;
  awayTeam: string | null;
  homeScore: number | null;
  awayScore: number | null;
  status: 'scheduled' | 'finished' | 'tbd';
  probHomeWin: number | null;
  probAwayWin: number | null;
}

interface BracketMatchProps {
  data: BracketMatchData;
  className?: string;
}

/**
 * One bracket node. Tappable when we have a match id; otherwise a static
 * placeholder ("待定 / TBD") that still occupies the same footprint so the
 * tree layout doesn't collapse before the draw.
 */
export function BracketMatch({ data, className }: BracketMatchProps) {
  const finished = data.status === 'finished';
  const tbd = data.status === 'tbd' || !data.homeTeam || !data.awayTeam;

  const inner = (
    <div
      className={cn(
        'flex w-44 flex-col gap-1 rounded-lg border bg-white p-2 text-xs shadow-sm',
        tbd ? 'border-slate-200 text-slate-400' : 'border-slate-300 text-slate-700',
        className,
      )}
    >
      <BracketRow
        team={data.homeTeam}
        score={finished ? data.homeScore : null}
        prob={!finished && !tbd ? data.probHomeWin : null}
        winner={finished && (data.homeScore ?? 0) > (data.awayScore ?? 0)}
      />
      <BracketRow
        team={data.awayTeam}
        score={finished ? data.awayScore : null}
        prob={!finished && !tbd ? data.probAwayWin : null}
        winner={finished && (data.awayScore ?? 0) > (data.homeScore ?? 0)}
      />
    </div>
  );

  if (tbd || !data.matchId) return inner;
  return (
    <Link href={`/match/${data.matchId}`} className="block hover:translate-y-[-1px] hover:shadow">
      {inner}
    </Link>
  );
}

function BracketRow({
  team,
  score,
  prob,
  winner,
}: {
  team: string | null;
  score: number | null;
  prob: number | null;
  winner: boolean;
}) {
  return (
    <div className="flex items-center justify-between">
      <span className={cn('truncate', winner ? 'font-bold text-slate-900' : '')}>
        {team ?? '待定'}
      </span>
      <span className="ml-2 shrink-0 tabular-nums">
        {score !== null ? score : prob !== null ? formatPercent(prob) : ''}
      </span>
    </div>
  );
}
