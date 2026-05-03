import type { Metadata } from 'next';

import { BracketView, type BracketRound } from '@/components/worldcup/BracketView';

export const metadata: Metadata = {
  title: '世界杯淘汰赛对阵图',
  description: '从 16 强到决赛的实时对阵 + AI 预测概率。',
};

// Phase 3.5: replace with /api/v1/competitions/worldcup/bracket data.
const PLACEHOLDER_ROUNDS: BracketRound[] = [
  {
    label: '16 强',
    matches: Array.from({ length: 8 }, () => ({
      matchId: null,
      homeTeam: null,
      awayTeam: null,
      homeScore: null,
      awayScore: null,
      status: 'tbd' as const,
      probHomeWin: null,
      probAwayWin: null,
    })),
  },
  {
    label: '8 强',
    matches: Array.from({ length: 4 }, () => ({
      matchId: null,
      homeTeam: null,
      awayTeam: null,
      homeScore: null,
      awayScore: null,
      status: 'tbd' as const,
      probHomeWin: null,
      probAwayWin: null,
    })),
  },
  {
    label: '4 强',
    matches: Array.from({ length: 2 }, () => ({
      matchId: null,
      homeTeam: null,
      awayTeam: null,
      homeScore: null,
      awayScore: null,
      status: 'tbd' as const,
      probHomeWin: null,
      probAwayWin: null,
    })),
  },
  {
    label: '决赛',
    matches: [
      {
        matchId: null,
        homeTeam: null,
        awayTeam: null,
        homeScore: null,
        awayScore: null,
        status: 'tbd' as const,
        probHomeWin: null,
        probAwayWin: null,
      },
    ],
  },
];

export default function BracketPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-slate-900">世界杯淘汰赛</h1>
      <BracketView rounds={PLACEHOLDER_ROUNDS} />
    </div>
  );
}
