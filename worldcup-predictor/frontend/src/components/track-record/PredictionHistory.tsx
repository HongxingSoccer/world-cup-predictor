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
        <CardBody className="text-sm text-slate-400">暂无历史预测记录。</CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <h3 className="text-sm font-semibold text-slate-100">历史预测</h3>
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
                {row.hit ? '✓ 红' : '✗ 黑'}
              </Badge>
            </div>
            <div className="mt-1 flex items-center justify-between">
              <div className="font-semibold text-slate-100">
                {row.homeTeam} <span className="text-slate-500">vs</span> {row.awayTeam}
              </div>
              <div className="text-sm text-slate-400">
                预测 <span className="font-semibold text-slate-100">{RESULT_LABEL[row.predicted]}</span>
                {' · '}实际 <span className="font-semibold text-slate-100">{RESULT_LABEL[row.actual]}</span>
              </div>
            </div>
            {row.pnlUnit !== 0 ? (
              <div
                className={`mt-1 text-xs tabular-nums ${
                  row.pnlUnit > 0 ? 'text-emerald-300' : 'text-rose-400'
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
