'use client';

import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { useT } from '@/i18n/I18nProvider';
import { formatPercent, formatSignedPercent } from '@/lib/utils';
import type { TrackRecordOverview } from '@/types';

interface MarketBreakdownProps {
  rows: TrackRecordOverview[];
}

const LABEL_KEY: Record<TrackRecordOverview['statType'], string> = {
  overall: 'trackRecord.marketOverall',
  '1x2': 'trackRecord.market1x2',
  score: 'trackRecord.marketScore',
  ou25: 'trackRecord.marketOu25',
  btts: 'trackRecord.marketBtts',
  positive_ev: 'trackRecord.marketPositiveEv',
};

export function MarketBreakdown({ rows }: MarketBreakdownProps) {
  const t = useT();
  return (
    <Card>
      <CardHeader>
        <h3 className="text-sm font-semibold text-slate-100">{t('trackRecord.byMarket')}</h3>
      </CardHeader>
      <CardBody className="overflow-x-auto p-0">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-900/60 text-xs uppercase tracking-wider text-slate-400">
            <tr>
              <th className="px-4 py-2 text-left">{t('trackRecord.tableMarket')}</th>
              <th className="px-4 py-2 text-right">{t('trackRecord.tableCount')}</th>
              <th className="px-4 py-2 text-right">{t('trackRecord.tableHitRate')}</th>
              <th className="px-4 py-2 text-right">{t('trackRecord.roi')}</th>
              <th className="px-4 py-2 text-right">{t('trackRecord.tableBestStreak')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={`${row.statType}-${row.period}`}
                className="border-t border-slate-800/70 transition-colors hover:bg-slate-800/30"
              >
                <td className="px-4 py-2 font-medium text-slate-100">{t(LABEL_KEY[row.statType])}</td>
                <td className="px-4 py-2 text-right tabular-nums text-slate-300">{row.totalPredictions}</td>
                <td className="px-4 py-2 text-right tabular-nums text-slate-300">{formatPercent(row.hitRate)}</td>
                <td
                  className={`px-4 py-2 text-right font-semibold tabular-nums ${row.roi >= 0 ? 'text-emerald-300' : 'text-rose-400'}`}
                >
                  {formatSignedPercent(row.roi)}
                </td>
                <td className="px-4 py-2 text-right tabular-nums text-slate-300">{row.bestStreak}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardBody>
    </Card>
  );
}
