/**
 * Score probability heatmap (Phase 5, design §6.1).
 *
 * Renders an 11×11 grid (0-10 home goals × 0-10 away goals) where each cell's
 * background lightness encodes the joint probability. Uses pure SVG + Tailwind
 * — no D3 dependency — so SSR works and bundle size stays tiny.
 *
 * Props:
 *   - `matrix`: number[][] — square probability matrix; values must sum to ~1.
 *   - `size`:   optional pixel size (default 360).
 *   - `lockBlurredCells`: payment-gate hint — when true, cells render as a
 *     uniform blurred block (see §6.1 "免费用户看模糊版").
 */
'use client';

import { useMemo, useState } from 'react';

import { useT } from '@/i18n/I18nProvider';

export type ScoreHeatmapProps = {
  matrix: number[][];
  size?: number;
  lockBlurredCells?: boolean;
};

const GRID = 11;

function colorForProb(p: number, max: number): string {
  // Tailwind emerald, lightness 95→25 mapped 0→max.
  if (max <= 0) return 'rgb(243 244 246)';
  const ratio = Math.min(1, p / max);
  const lightness = Math.round(95 - ratio * 70); // 95 → 25
  return `hsl(152 60% ${lightness}%)`;
}

export function ScoreHeatmap({ matrix, size = 360, lockBlurredCells = false }: ScoreHeatmapProps) {
  const t = useT();
  const flat = useMemo(() => matrix.flat(), [matrix]);
  const max = useMemo(() => flat.reduce((m, v) => (v > m ? v : m), 0), [flat]);
  const [hover, setHover] = useState<{ h: number; a: number; p: number } | null>(null);

  const cell = size / (GRID + 1);

  return (
    <figure className="inline-block" aria-label={t('viz.heatmap.title', 'Score heatmap')}>
      <figcaption className="mb-2 text-sm font-medium text-slate-300">
        {t('viz.heatmap.title', 'Score heatmap')}
      </figcaption>
      <svg width={size} height={size} role="img" className="overflow-visible">
        {/* Axis labels */}
        <text x={size / 2} y={cell * 0.6} textAnchor="middle" className="fill-slate-500" style={{ fontSize: 11 }}>
          {t('viz.heatmap.away', 'Away goals')}
        </text>
        <text
          x={cell * 0.4}
          y={size / 2}
          textAnchor="middle"
          className="fill-slate-500"
          style={{ fontSize: 11 }}
          transform={`rotate(-90 ${cell * 0.4} ${size / 2})`}
        >
          {t('viz.heatmap.home', 'Home goals')}
        </text>
        {/* Cells */}
        {matrix.slice(0, GRID).map((row, i) =>
          row.slice(0, GRID).map((p, j) => {
            const x = (j + 1) * cell;
            const y = (i + 1) * cell;
            const fill = lockBlurredCells ? 'hsl(152 30% 80%)' : colorForProb(p, max);
            return (
              <rect
                key={`${i}-${j}`}
                x={x}
                y={y}
                width={cell - 1}
                height={cell - 1}
                fill={fill}
                onMouseEnter={() => setHover({ h: i, a: j, p })}
                onMouseLeave={() => setHover(null)}
                style={lockBlurredCells ? { filter: 'blur(2px)' } : undefined}
              />
            );
          }),
        )}
        {/* Tick labels (0..10) */}
        {Array.from({ length: GRID }).map((_, k) => (
          <g key={`tick-${k}`}>
            <text
              x={(k + 1) * cell + cell / 2}
              y={cell - 4}
              textAnchor="middle"
              className="fill-slate-500"
              style={{ fontSize: 10 }}
            >
              {k}
            </text>
            <text
              x={cell - 6}
              y={(k + 1) * cell + cell / 2 + 3}
              textAnchor="end"
              className="fill-slate-500"
              style={{ fontSize: 10 }}
            >
              {k}
            </text>
          </g>
        ))}
      </svg>
      {hover && !lockBlurredCells && (
        <div className="mt-2 text-xs text-slate-400" role="status">
          <span className="font-mono">
            {hover.h}-{hover.a}
          </span>{' '}
          · {t('viz.heatmap.probability', 'Probability')}: {(hover.p * 100).toFixed(2)}%
        </div>
      )}
    </figure>
  );
}
