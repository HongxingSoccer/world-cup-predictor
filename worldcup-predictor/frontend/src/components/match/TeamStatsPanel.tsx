import { Card, CardBody, CardHeader } from '@/components/ui/Card';

interface StatRow {
  label: string;
  home: number | string;
  away: number | string;
}

interface TeamStatsPanelProps {
  homeTeam: string;
  awayTeam: string;
  rows: StatRow[];
}

/**
 * Side-by-side comparison of head-to-head numeric stats. Pure presentation —
 * the parent computes the rows so we can A/B different stat sets without
 * touching this component.
 */
export function TeamStatsPanel({ homeTeam, awayTeam, rows }: TeamStatsPanelProps) {
  return (
    <Card>
      <CardHeader>
        <h3 className="text-sm font-semibold text-slate-900">两队数据对比</h3>
      </CardHeader>
      <CardBody>
        <div className="mb-2 grid grid-cols-3 text-xs uppercase tracking-wider text-slate-500">
          <div className="text-right">{homeTeam}</div>
          <div className="text-center">指标</div>
          <div className="text-left">{awayTeam}</div>
        </div>
        <div className="divide-y divide-slate-100">
          {rows.map((row) => (
            <div key={row.label} className="grid grid-cols-3 items-center py-2 text-sm">
              <div className="text-right font-semibold tabular-nums text-slate-900">
                {row.home}
              </div>
              <div className="text-center text-slate-500">{row.label}</div>
              <div className="text-left font-semibold tabular-nums text-slate-900">
                {row.away}
              </div>
            </div>
          ))}
        </div>
      </CardBody>
    </Card>
  );
}
