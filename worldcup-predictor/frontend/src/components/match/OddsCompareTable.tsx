import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { ValueSignalBadge } from '@/components/prediction/ValueSignalBadge';
import { formatPercent, formatSignedPercent } from '@/lib/utils';
import type { SignalLevel } from '@/types';

/** Single row from `odds_analysis` exposed via the Java API. */
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

/**
 * Tabular view of every value-signal row. Sorted by `signalLevel` then `ev`
 * before rendering so the most actionable rows are at the top.
 */
export function OddsCompareTable({ rows }: OddsCompareTableProps) {
  const sorted = [...rows].sort(
    (a, b) => b.signalLevel - a.signalLevel || b.ev - a.ev,
  );

  if (sorted.length === 0) {
    return (
      <Card>
        <CardBody className="text-sm text-slate-500">暂无可分析的赔率数据。</CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <h3 className="text-sm font-semibold text-slate-900">赔率价值分析</h3>
        <span className="text-xs text-slate-500">最佳赔率 + 模型概率对比</span>
      </CardHeader>
      <CardBody className="overflow-x-auto p-0">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
            <tr>
              <th className="px-4 py-2 text-left">盘口</th>
              <th className="px-4 py-2 text-left">选项</th>
              <th className="px-4 py-2 text-right">模型</th>
              <th className="px-4 py-2 text-right">赔率</th>
              <th className="px-4 py-2 text-left">公司</th>
              <th className="px-4 py-2 text-right">EV</th>
              <th className="px-4 py-2 text-right">Edge</th>
              <th className="px-4 py-2 text-right">信号</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, idx) => (
              <tr key={idx} className="border-t border-slate-100">
                <td className="whitespace-nowrap px-4 py-2 text-slate-600">
                  {row.marketValue ? `${row.marketType} · ${row.marketValue}` : row.marketType}
                </td>
                <td className="px-4 py-2 font-semibold text-slate-900">{row.outcome}</td>
                <td className="px-4 py-2 text-right tabular-nums text-slate-700">
                  {formatPercent(row.modelProb)}
                </td>
                <td className="px-4 py-2 text-right tabular-nums font-semibold text-slate-900">
                  {row.bestOdds.toFixed(2)}
                </td>
                <td className="px-4 py-2">
                  <Badge tone="info">{row.bestBookmaker}</Badge>
                </td>
                <td
                  className={`px-4 py-2 text-right tabular-nums font-semibold ${row.ev >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}
                >
                  {formatSignedPercent(row.ev)}
                </td>
                <td className="px-4 py-2 text-right tabular-nums text-slate-700">
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
