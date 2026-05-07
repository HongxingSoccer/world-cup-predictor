/**
 * Knockout-stage bracket (Phase 5, design §6.2).
 *
 * Renders the 16→8→4→Final tree as an SVG. Each node shows the two teams +
 * the model's predicted winner probability; finished games show the actual
 * score. Hovering a node calls `onHover` so the parent can highlight a team's
 * full path. Pure SVG keeps the bundle tiny and SSR-safe.
 */
'use client';

import { useState } from 'react';

import { useT } from '@/i18n/I18nProvider';

export type BracketTeam = {
  id: number;
  name: string;
};

export type BracketMatch = {
  id: string;
  round: 'r16' | 'qf' | 'sf' | 'final';
  home: BracketTeam | null;
  away: BracketTeam | null;
  homeScore?: number | null;
  awayScore?: number | null;
  /** Model probability of `home` advancing (0..1). */
  probHomeAdvance?: number;
};

export type BracketProps = {
  matches: BracketMatch[];
  onHover?: (teamId: number | null) => void;
};

const ROUND_ORDER: BracketMatch['round'][] = ['r16', 'qf', 'sf', 'final'];
const ROUND_X = [40, 220, 400, 580];
const NODE_W = 160;
const NODE_H = 56;

function nodeY(roundIdx: number, idxInRound: number, totalInRound: number, height: number): number {
  const slot = height / (totalInRound + 1);
  return slot * (idxInRound + 1) - NODE_H / 2;
}

export function KnockoutBracket({ matches, onHover }: BracketProps) {
  const t = useT();
  const [highlighted, setHighlighted] = useState<number | null>(null);

  const byRound = ROUND_ORDER.map((r) => matches.filter((m) => m.round === r));
  const height = Math.max(360, byRound[0].length * 60);
  const width = 760;

  const handleHover = (teamId: number | null) => {
    setHighlighted(teamId);
    onHover?.(teamId);
  };

  return (
    <figure className="overflow-x-auto" aria-label={t('viz.bracket.title', 'Knockout bracket')}>
      <figcaption className="mb-2 text-sm font-medium text-slate-300">
        {t('viz.bracket.title', 'Knockout bracket')}
      </figcaption>
      <svg width={width} height={height} role="img">
        {byRound.map((roundMatches, roundIdx) => {
          const x = ROUND_X[roundIdx];
          return roundMatches.map((m, i) => {
            const y = nodeY(roundIdx, i, roundMatches.length, height);
            const isHighlighted =
              highlighted !== null &&
              (m.home?.id === highlighted || m.away?.id === highlighted);
            const stroke = isHighlighted ? '#16a34a' : '#cbd5e1';
            return (
              <g key={m.id} transform={`translate(${x} ${y})`}>
                <rect
                  width={NODE_W}
                  height={NODE_H}
                  rx={6}
                  ry={6}
                  fill="white"
                  stroke={stroke}
                  strokeWidth={isHighlighted ? 2 : 1}
                />
                <text
                  x={8}
                  y={20}
                  className="fill-slate-800"
                  style={{ fontSize: 12, fontWeight: 600 }}
                  onMouseEnter={() => m.home && handleHover(m.home.id)}
                  onMouseLeave={() => handleHover(null)}
                >
                  {m.home?.name ?? '—'}
                  {m.homeScore != null ? `  ${m.homeScore}` : ''}
                </text>
                <text
                  x={8}
                  y={42}
                  className="fill-slate-800"
                  style={{ fontSize: 12, fontWeight: 600 }}
                  onMouseEnter={() => m.away && handleHover(m.away.id)}
                  onMouseLeave={() => handleHover(null)}
                >
                  {m.away?.name ?? '—'}
                  {m.awayScore != null ? `  ${m.awayScore}` : ''}
                </text>
                {m.probHomeAdvance != null && m.homeScore == null && (
                  <text
                    x={NODE_W - 8}
                    y={NODE_H - 6}
                    textAnchor="end"
                    className="fill-emerald-700"
                    style={{ fontSize: 10 }}
                  >
                    {t('viz.bracket.qualifyProb', 'Qualify prob.')}{' '}
                    {(m.probHomeAdvance * 100).toFixed(0)}%
                  </text>
                )}
              </g>
            );
          });
        })}
      </svg>
    </figure>
  );
}
