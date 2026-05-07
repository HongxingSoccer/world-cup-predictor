'use client';

import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { ValueSignalBadge } from '@/components/prediction/ValueSignalBadge';
import { useT } from '@/i18n/I18nProvider';
import { formatPercent, formatSignedPercent } from '@/lib/utils';
import type { SignalLevel } from '@/types';

export interface OddsRow {
  marketType: string;
  marketValue: string | null;
  outcome: string;
  modelProb: number;
  bestOdds: number;
  bestBookmaker: string;
  impliedProb: number;
  ev: number;
  edge: number;
  signalLevel: SignalLevel;
}

interface OddsCompareTableProps {
  rows: OddsRow[];
}

export function OddsCompareTable({ rows }: OddsCompareTableProps) {
  const t = useT();
  const sorted = [...rows].sort(
    (a, b) => b.signalLevel - a.signalLevel || b.ev - a.ev,
  );

  if (sorted.length === 0) {
    return (
      <Card>
        <CardBody className="text-sm text-slate-400">{t('match.oddsEmpty')}</CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <h3 className="text-sm font-semibold text-slate-100">{t('match.oddsAnalysis')}</h3>
        <span className="text-xs text-slate-400">{t('match.oddsSubtitle')}</span>
      </CardHeader>
      <CardBody className="overflow-x-auto p-0">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-900/60 text-xs uppercase tracking-wider text-slate-400">
            <tr>
              <th className="px-4 py-2 text-left">{t('match.market')}</th>
              <th className="px-4 py-2 text-left">{t('match.outcome')}</th>
              <th className="px-4 py-2 text-right">{t('match.model')}</th>
              <th className="px-4 py-2 text-right">{t('match.odds')}</th>
              <th className="px-4 py-2 text-left">{t('match.bookmaker')}</th>
              <th className="px-4 py-2 text-right">EV</th>
              <th className="px-4 py-2 text-right">Edge</th>
              <th className="px-4 py-2 text-right">{t('match.signal')}</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, idx) => (
              <tr
                key={idx}
                className="border-t border-slate-800/70 transition-colors hover:bg-slate-800/30"
              >
                <td className="whitespace-nowrap px-4 py-2 text-slate-400">
                  {row.marketValue ? `${row.marketType} · ${row.marketValue}` : row.marketType}
                </td>
                <td className="px-4 py-2 font-semibold text-slate-100">{row.outcome}</td>
                <td className="px-4 py-2 text-right tabular-nums text-slate-300">
                  {formatPercent(row.modelProb)}
                </td>
                <td className="px-4 py-2 text-right tabular-nums font-semibold text-slate-100">
                  {row.bestOdds.toFixed(2)}
                </td>
                <td className="px-4 py-2">
                  <Badge tone="info">{row.bestBookmaker}</Badge>
                </td>
                <td
                  className={`px-4 py-2 text-right tabular-nums font-semibold ${row.ev >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}
                >
                  {formatSignedPercent(row.ev)}
                </td>
                <td className="px-4 py-2 text-right tabular-nums text-slate-300">
                  {formatSignedPercent(row.edge)}
                </td>
                <td className="px-4 py-2 text-right">
                  <ValueSignalBadge level={row.signalLevel} hideEmpty />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardBody>
    </Card>
  );
}
