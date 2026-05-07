'use client';

import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { useT } from '@/i18n/I18nProvider';
import { formatPercent } from '@/lib/utils';

export interface H2HSummary {
  totalMatches: number;
  homeWins: number;
  draws: number;
  awayWins: number;
  avgGoals: number;
}

interface H2HPanelProps {
  homeTeam: string;
  awayTeam: string;
  summary: H2HSummary;
}

export function H2HPanel({ homeTeam, awayTeam, summary }: H2HPanelProps) {
  const t = useT();
  const total = Math.max(summary.totalMatches, 1);
  const homeRate = summary.homeWins / total;
  const drawRate = summary.draws / total;
  const awayRate = summary.awayWins / total;

  if (summary.totalMatches === 0) {
    return (
      <Card>
        <CardHeader>
          <h3 className="text-sm font-semibold text-slate-100">{t('match.h2h')}</h3>
          <span className="text-xs text-slate-400">{t('match.h2hEmpty')}</span>
        </CardHeader>
        <CardBody>
          <div className="py-6 text-center text-sm text-slate-500">{t('match.h2hNoRecords')}</div>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <h3 className="text-sm font-semibold text-slate-100">{t('match.h2h')}</h3>
        <span className="text-xs text-slate-400">
          {t('match.h2hCount').replace('{count}', String(summary.totalMatches))}
        </span>
      </CardHeader>
      <CardBody className="space-y-3">
        <div className="flex h-3 overflow-hidden rounded-full bg-slate-800/80 ring-1 ring-slate-700/60">
          <div className="bg-emerald-500/90" style={{ width: `${homeRate * 100}%` }} />
          <div className="bg-amber-400/90" style={{ width: `${drawRate * 100}%` }} />
          <div className="bg-rose-500/90" style={{ width: `${awayRate * 100}%` }} />
        </div>
        <div className="grid grid-cols-3 text-center text-xs">
          <Cell
            label={`${homeTeam}${t('match.winSuffix')}`}
            value={`${summary.homeWins} (${formatPercent(homeRate)})`}
          />
          <Cell
            label={t('match.drawFull')}
            value={`${summary.draws} (${formatPercent(drawRate)})`}
          />
          <Cell
            label={`${awayTeam}${t('match.winSuffix')}`}
            value={`${summary.awayWins} (${formatPercent(awayRate)})`}
          />
        </div>
        <div className="mt-2 text-center text-sm text-slate-400">
          {t('match.avgGoals')}{' '}
          <span className="font-semibold tabular-nums text-slate-100">
            {summary.avgGoals.toFixed(2)}
          </span>
        </div>
      </CardBody>
    </Card>
  );
}

function Cell({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-slate-500">{label}</div>
      <div className="font-semibold tabular-nums text-slate-100">{value}</div>
    </div>
  );
}
