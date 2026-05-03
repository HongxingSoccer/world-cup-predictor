import Link from 'next/link';

import { Badge } from '@/components/ui/Badge';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
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

const RESULT_LABEL: Record<'H' | 'D' | 'A', string> = { H: '主胜', D: '平', A: '客胜' };

export function PredictionHistory({ rows }: PredictionHistoryProps) {
  if (rows.length === 0) {
    return (
      <Card>
        <CardBody className="text-sm text-slate-500">暂无历史预测记录。</CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <h3 className="text-sm font-semibold text-slate-900">历史预测</h3>
      </CardHeader>
      <CardBody className="divide-y divide-slate-100 p-0">
        {rows.map((row) => (
          <Link
            key={row.matchId}
            href={`/match/${row.matchId}`}
            className="block px-4 py-3 transition hover:bg-slate-50"
          >
            <div className="flex items-center justify-between text-xs text-slate-500">
              <span>{formatMatchDate(row.matchDate)}</span>
              <Badge tone={row.hit ? 'success' : 'danger'}>
                {row.hit ? '✓ 红' : '✗ 黑'}
              </Badge>
            </div>
            <div className="mt-1 flex items-center justify-between">
              <div className="font-semibold text-slate-900">
                {row.homeTeam} <span className="text-slate-400">vs</span> {row.awayTeam}
              </div>
              <div className="text-sm text-slate-600">
                预测 <span className="font-semibold text-slate-900">{RESULT_LABEL[row.predicted]}</span>
                {' · '}实际 <span className="font-semibold text-slate-900">{RESULT_LABEL[row.actual]}</span>
              </div>
            </div>
            {row.pnlUnit !== 0 ? (
              <div
                className={`mt-1 text-xs tabular-nums ${
                  row.pnlUnit > 0 ? 'text-emerald-600' : 'text-rose-600'
                }`}
              >
                {row.pnlUnit > 0 ? '+' : ''}
                {row.pnlUnit.toFixed(2)} 单位
              </div>
            ) : null}
          </Link>
        ))}
      </CardBody>
    </Card>
  );
}
