import { TeamLogo } from '@/components/match/TeamLogo';
import { Card, CardBody } from '@/components/ui/Card';
import { formatMatchDate } from '@/lib/utils';
import type { MatchSummary } from '@/types';

interface MatchHeaderProps {
  match: MatchSummary;
}

export function MatchHeader({ match }: MatchHeaderProps) {
  const finished = match.status === 'finished';
  const score =
    finished &&
    match.homeScore !== null &&
    match.homeScore !== undefined &&
    match.awayScore !== null &&
    match.awayScore !== undefined
      ? `${match.homeScore} - ${match.awayScore}`
      : null;
  return (
    <Card className="overflow-hidden">
      <CardBody>
        <div className="flex items-center justify-between text-xs uppercase tracking-widest text-slate-400">
          <span>{match.competition ?? '比赛'}</span>
          {match.round ? <span className="text-slate-500">{match.round}</span> : null}
        </div>
        <div className="mt-4 flex items-center justify-between gap-3 sm:gap-6">
          <Side
            name={match.homeTeam}
            logo={match.homeTeamLogo}
            role="主队"
            align="right"
          />
          <div className="text-center">
            {score ? (
              <div className="hero-number text-3xl font-black tabular-nums sm:text-4xl">
                {score}
              </div>
            ) : (
              <div className="text-xs uppercase tracking-widest text-brand-400">
                VS
              </div>
            )}
            <div className="mt-1 text-xs font-medium tabular-nums text-slate-400 sm:text-sm">
              {formatMatchDate(match.matchDate)}
            </div>
          </div>
          <Side
            name={match.awayTeam}
            logo={match.awayTeamLogo}
            role="客队"
            align="left"
          />
        </div>
      </CardBody>
    </Card>
  );
}

function Side({
  name,
  logo,
  role,
  align,
}: {
  name: string;
  logo?: string | null;
  role: string;
  align: 'left' | 'right';
}) {
  return (
    <div
      className={
        align === 'right'
          ? 'flex flex-1 flex-col items-end gap-2 text-right sm:flex-row sm:items-center sm:justify-end sm:gap-3'
          : 'flex flex-1 flex-col items-start gap-2 text-left sm:flex-row-reverse sm:items-center sm:justify-end sm:gap-3'
      }
    >
      <TeamLogo src={logo} name={name} size="lg" />
      <div className={align === 'right' ? 'text-right' : 'text-left'}>
        <div className="text-base font-bold tracking-tight text-slate-100 sm:text-xl">
          {name}
        </div>
        <div className="text-xs text-slate-500">{role}</div>
      </div>
    </div>
  );
}
