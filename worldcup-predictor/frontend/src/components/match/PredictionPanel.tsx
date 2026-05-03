import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { clampProb, formatPercent } from '@/lib/utils';
import type { MatchSummary } from '@/types';

interface PredictionPanelProps {
  match: MatchSummary;
}

/**
 * Tier-blind primary view of the 1x2 distribution. Always renders, even for
 * free users — it's the most basic signal we expose.
 */
export function PredictionPanel({ match }: PredictionPanelProps) {
  const home = clampProb(match.probHomeWin);
  const draw = clampProb(match.probDraw);
  const away = clampProb(match.probAwayWin);

  return (
    <Card>
      <CardHeader>
        <div>
          <h3 className="text-sm font-semibold text-slate-900">胜平负预测</h3>
          <p className="mt-0.5 text-xs text-slate-500">基于 Poisson 模型 + Elo 修正</p>
        </div>
        <div className="text-right text-xs text-slate-500">
          <div>置信度</div>
          <div className="text-lg font-bold text-slate-900">{match.confidenceScore ?? '—'}</div>
        </div>
      </CardHeader>
      <CardBody className="space-y-3">
        <Row label={`${match.homeTeam} 胜`} value={home} barClass="bg-emerald-500" />
        <Row label="平局" value={draw} barClass="bg-amber-400" />
        <Row label={`${match.awayTeam} 胜`} value={away} barClass="bg-rose-500" />
      </CardBody>
    </Card>
  );
}

function Row({ label, value, barClass }: { label: string; value: number; barClass: string }) {
  const pct = (value * 100).toFixed(1);
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="text-slate-700">{label}</span>
        <span className="font-semibold text-slate-900">{formatPercent(value)}</span>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full bg-slate-100"
        role="progressbar"
        aria-valuenow={Number(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div className={`${barClass} h-full`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
