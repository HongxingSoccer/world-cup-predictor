import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { formatPercent, formatSignedPercent } from '@/lib/utils';
import type { TrackRecordOverview } from '@/types';

interface MarketBreakdownProps {
  rows: TrackRecordOverview[];
}

const STAT_LABEL: Record<TrackRecordOverview['statType'], string> = {
  overall: '总体',
  '1x2': '胜平负',
  score: '比分',
  ou25: '大小球 2.5',
  btts: '双方进球',
  positive_ev: '正 EV',
};

export function MarketBreakdown({ rows }: MarketBreakdownProps) {
  return (
    <Card>
      <CardHeader>
        <h3 className="text-sm font-semibold text-slate-900">按盘口分层</h3>
      </CardHeader>
      <CardBody className="overflow-x-auto p-0">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
            <tr>
              <th className="px-4 py-2 text-left">盘口</th>
              <th className="px-4 py-2 text-right">场次</th>
              <th className="px-4 py-2 text-right">命中率</th>
              <th className="px-4 py-2 text-right">ROI</th>
              <th className="px-4 py-2 text-right">最佳连红</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.statType}-${row.period}`} className="border-t border-slate-100">
                <td className="px-4 py-2 font-medium text-slate-900">{STAT_LABEL[row.statType]}</td>
                <td className="px-4 py-2 text-right tabular-nums">{row.totalPredictions}</td>
                <td className="px-4 py-2 text-right tabular-nums">{formatPercent(row.hitRate)}</td>
                <td
                  className={`px-4 py-2 text-right font-semibold tabular-nums ${row.roi >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}
                >
                  {formatSignedPercent(row.roi)}
                </td>
                <td className="px-4 py-2 text-right tabular-nums">{row.bestStreak}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardBody>
    </Card>
  );
}
