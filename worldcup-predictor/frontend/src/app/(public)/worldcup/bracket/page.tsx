import type { Metadata } from 'next';

import { Card, CardBody } from '@/components/ui/Card';
import { BracketView, type BracketRound } from '@/components/worldcup/BracketView';
import type { BracketMatchData } from '@/components/worldcup/BracketMatch';

export const metadata: Metadata = {
  title: '世界杯淘汰赛对阵图',
  description: '从 32 强到决赛的实时对阵 + AI 预测概率。',
};

// Render on every request — bracket fills in as group stage finishes.
export const dynamic = 'force-dynamic';

interface ApiBracketMatch {
  match_id: number | null;
  match_date?: string | null;
  home_team: string | null;
  away_team: string | null;
  home_score: number | null;
  away_score: number | null;
  status: 'scheduled' | 'finished' | 'tbd';
  prob_home_win: number | null;
  prob_away_win: number | null;
}

interface ApiBracketRound {
  label: string;
  matches: ApiBracketMatch[];
}

interface ApiBracketResponse {
  competition: string;
  year: number;
  rounds: ApiBracketRound[];
  generated_at?: string;
}

async function fetchBracket(): Promise<ApiBracketRound[]> {
  const baseUrl =
    process.env.SERVER_API_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    'http://localhost:8080';
  const url = new URL('/api/v1/competitions/worldcup/bracket', baseUrl);
  try {
    const response = await fetch(url.toString(), { next: { revalidate: 120 } });
    if (!response.ok) return [];
    const body = (await response.json()) as ApiBracketResponse;
    return body.rounds ?? [];
  } catch {
    return [];
  }
}

function toMatch(api: ApiBracketMatch): BracketMatchData {
  return {
    matchId: api.match_id,
    homeTeam: api.home_team,
    awayTeam: api.away_team,
    homeScore: api.home_score,
    awayScore: api.away_score,
    status: api.status,
    probHomeWin: api.prob_home_win,
    probAwayWin: api.prob_away_win,
  };
}

export default async function BracketPage() {
  const apiRounds = await fetchBracket();
  const rounds: BracketRound[] = apiRounds.map((r) => ({
    label: r.label,
    matches: r.matches.map(toMatch),
  }));

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-slate-100">世界杯淘汰赛</h1>
      {rounds.length === 0 ? (
        <Card>
          <CardBody className="text-center text-sm text-slate-400">
            暂无淘汰赛数据。
          </CardBody>
        </Card>
      ) : (
        <BracketView rounds={rounds} />
      )}
    </div>
  );
}
