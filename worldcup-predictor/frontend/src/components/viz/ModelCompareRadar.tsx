/**
 * Multi-model comparison radar (Phase 5, design §6.3).
 *
 * Side-by-side view of the 4 underlying models on 6 dimensions
 * (P_home, P_draw, P_away, λ_home, λ_away, P_BTTS). Built on Recharts so it
 * stays responsive across device sizes.
 */
'use client';

import {
  Legend,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';

import { useT } from '@/i18n/I18nProvider';

export type ModelOutput = {
  name: 'poisson' | 'dixonColes' | 'xgboost' | 'ensemble';
  probHomeWin: number;
  probDraw: number;
  probAwayWin: number;
  lambdaHome: number;
  lambdaAway: number;
  bttsProb: number;
};

export type ModelCompareProps = {
  outputs: ModelOutput[];
  height?: number;
};

const COLORS: Record<ModelOutput['name'], string> = {
  poisson: '#0ea5e9',
  dixonColes: '#8b5cf6',
  xgboost: '#f97316',
  ensemble: '#16a34a',
};

export function ModelCompareRadar({ outputs, height = 360 }: ModelCompareProps) {
  const t = useT();
  const data = [
    { axis: 'P(home)', ...byModel(outputs, (o) => o.probHomeWin) },
    { axis: 'P(draw)', ...byModel(outputs, (o) => o.probDraw) },
    { axis: 'P(away)', ...byModel(outputs, (o) => o.probAwayWin) },
    { axis: 'λ home', ...byModel(outputs, (o) => Math.min(1, o.lambdaHome / 4)) },
    { axis: 'λ away', ...byModel(outputs, (o) => Math.min(1, o.lambdaAway / 4)) },
    { axis: 'BTTS', ...byModel(outputs, (o) => o.bttsProb) },
  ];

  return (
    <figure className="w-full" aria-label={t('viz.compare.title', 'Model comparison')}>
      <figcaption className="mb-2 text-sm font-medium text-slate-300">
        {t('viz.compare.title', 'Model comparison')}
      </figcaption>
      <div style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={data}>
            <PolarGrid />
            <PolarAngleAxis dataKey="axis" />
            <PolarRadiusAxis angle={30} domain={[0, 1]} tickCount={5} />
            {outputs.map((o) => (
              <Radar
                key={o.name}
                name={t(`viz.compare.${o.name}`, o.name)}
                dataKey={o.name}
                stroke={COLORS[o.name]}
                fill={COLORS[o.name]}
                fillOpacity={0.15}
              />
            ))}
            <Tooltip />
            <Legend />
          </RadarChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}

function byModel(outputs: ModelOutput[], pick: (o: ModelOutput) => number): Record<string, number> {
  return Object.fromEntries(outputs.map((o) => [o.name, Number(pick(o).toFixed(4))]));
}
