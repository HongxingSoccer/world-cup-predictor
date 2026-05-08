'use client';

import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { useT } from '@/i18n/I18nProvider';
import { clampProb, formatPercent } from '@/lib/utils';
import type { MatchSummary } from '@/types';

interface PredictionPanelProps {
  match: MatchSummary;
}

export function PredictionPanel({ match }: PredictionPanelProps) {
  const t = useT();
  const home = clampProb(match.probHomeWin);
  const draw = clampProb(match.probDraw);
  const away = clampProb(match.probAwayWin);

  return (
    <Card>
      <CardHeader>
        <div>
          <h3 className="text-sm font-semibold text-slate-100">{t('match.predictionTitle')}</h3>
          <p className="mt-0.5 text-xs text-slate-400">{t('match.predictionSubtitle')}</p>
        </div>
        <div className="text-right text-xs text-slate-400">
          <div>{t('match.confidence')}</div>
          <div className="hero-number text-2xl font-bold">{match.confidenceScore ?? '—'}</div>
        </div>
      </CardHeader>
      <CardBody className="space-y-3">
        <Row label={`${match.homeTeam}${t('match.winSuffix')}`} value={home} barClass="bg-emerald-500" />
        <Row label={t('match.drawFull')} value={draw} barClass="bg-amber-400" />
        <Row label={`${match.awayTeam}${t('match.winSuffix')}`} value={away} barClass="bg-rose-500" />
      </CardBody>
    </Card>
  );
}

function Row({ label, value, barClass }: { label: string; value: number; barClass: string }) {
  const pct = (value * 100).toFixed(1);
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-sm">
        <span className="text-slate-300">{label}</span>
        <span className="font-semibold tabular-nums text-slate-100">{formatPercent(value)}</span>
      </div>
      <div
        className="h-2 overflow-hidden rounded-full bg-slate-800/80 ring-1 ring-slate-700/60"
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
