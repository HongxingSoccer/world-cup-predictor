import { Card, CardBody } from '@/components/ui/Card';
import { formatMatchDate } from '@/lib/utils';
import type { MatchSummary } from '@/types';

interface MatchHeaderProps {
  match: MatchSummary;
}

export function MatchHeader({ match }: MatchHeaderProps) {
  return (
    <Card className="overflow-hidden">
      <CardBody>
        <div className="text-xs text-slate-500">{match.competition ?? '比赛'}</div>
        <div className="mt-3 flex items-center justify-between gap-4">
          <Side name={match.homeTeam} role="主队" />
          <div className="text-center">
            <div className="text-xs uppercase tracking-widest text-slate-400">
              {match.status === 'finished' ? 'FT' : 'VS'}
            </div>
            <div className="mt-1 text-base font-medium text-slate-700">
              {formatMatchDate(match.matchDate)}
            </div>
          </div>
          <Side name={match.awayTeam} role="客队" align="left" />
        </div>
      </CardBody>
    </Card>
  );
}

function Side({
  name,
  role,
  align = 'right',
}: {
  name: string;
  role: string;
  align?: 'left' | 'right';
}) {
  return (
    <div className={align === 'right' ? 'flex-1 text-right' : 'flex-1 text-left'}>
      <div className="text-xl font-bold text-slate-900 sm:text-2xl">{name}</div>
      <div className="text-xs text-slate-500">{role}</div>
    </div>
  );
}
