'use client';

import Link from 'next/link';

import { Badge } from '@/components/ui/Badge';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { useT } from '@/i18n/I18nProvider';
import { formatMatchDate } from '@/lib/utils';

export interface PredictionHistoryRow {
  matchId: number;
  matchDate: string;
  homeTeam: string;
  awayTeam: string;
  predicted: 'H' | 'D' | 'A';
  actual: 'H' | 'D' | 'A';
  hit: boolean;
  pnlUnit: number;
}

interface PredictionHistoryProps {
  rows: PredictionHistoryRow[];
}

export function PredictionHistory({ rows }: PredictionHistoryProps) {
  const t = useT();
  const RESULT_LABEL: Record<'H' | 'D' | 'A', string> = {
    H: t('match.homeWin'),
    D: t('trackRecord.predicted') === '预测' ? '平' : t('match.draw'),
    A: t('match.awayWin'),
  };
  // The above ternary is a quick zh/en check via translation result; cleaner:
  RESULT_LABEL.D = t('match.draw');

  if (rows.length === 0) {
    return (
      <Card>
        <CardBody className="text-sm text-slate-400">{t('trackRecord.noHistoryRecords')}</CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <h3 className="text-sm font-semibold text-slate-100">{t('trackRecord.history')}</h3>
      </CardHeader>
      <CardBody className="divide-y divide-slate-800/70 p-0">
        {rows.map((row) => (
          <Link
            key={row.matchId}
            href={`/match/${row.matchId}`}
            className="block px-4 py-3 transition hover:bg-slate-800/30"
          >
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span className="tabular-nums">{formatMatchDate(row.matchDate)}</span>
              <Badge tone={row.hit ? 'success' : 'danger'}>
                {row.hit ? t('trackRecord.hitMark') : t('trackRecord.missMark')}
              </Badge>
            </div>
            <div className="mt-1 flex items-center justify-between">
              <div className="font-semibold text-slate-100">
                {row.homeTeam} <span className="text-slate-500">{t('match.vs')}</span> {row.awayTeam}
              </div>
              <div className="text-sm text-slate-400">
                {t('trackRecord.predicted')}{' '}
                <span className="font-semibold text-slate-100">{RESULT_LABEL[row.predicted]}</span>
                {' · '}
                {t('trackRecord.actual')}{' '}
                <span className="font-semibold text-slate-100">{RESULT_LABEL[row.actual]}</span>
              </div>
            </div>
            {row.pnlUnit !== 0 ? (
              <div
                className={`mt-1 text-xs tabular-nums ${
                  row.pnlUnit > 0 ? 'text-emerald-300' : 'text-rose-400'
                }`}
              >
                {row.pnlUnit > 0 ? '+' : ''}
                {row.pnlUnit.toFixed(2)} {t('trackRecord.cumulativeUnit')}
              </div>
            ) : null}
          </Link>
        ))}
      </CardBody>
    </Card>
  );
}
