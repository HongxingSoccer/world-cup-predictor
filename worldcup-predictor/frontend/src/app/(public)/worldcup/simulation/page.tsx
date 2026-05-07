import type { Metadata } from 'next';

import { Card, CardBody } from '@/components/ui/Card';
import {
  ChampionLeaderboard,
  type ChampionLeaderboardRow,
} from '@/components/worldcup/ChampionLeaderboard';

export const metadata: Metadata = {
  title: '世界杯夺冠概率',
  description: '蒙特卡洛模拟下的 2026 世界杯夺冠 / 亚军 / 季军 / 殿军概率榜。',
};

export const dynamic = 'force-dynamic';

interface ApiSimulationLeaderboardEntry {
  team_id: number;
  team_name: string;
  team_name_zh: string | null;
  champion_prob: number;
  runner_up_prob: number;
  third_prob: number;
  fourth_prob: number;
  top4_prob: number;
  qualify_prob: number;
}

interface ApiSimulationResponse {
  id?: number;
  simulation_version?: string;
  num_simulations?: number;
  model_version?: string;
  computed_at?: string;
  results?: {
    leaderboard?: ApiSimulationLeaderboardEntry[];
    trials?: number;
  };
}

async function fetchSimulation(): Promise<ApiSimulationResponse | null> {
  const baseUrl =
    process.env.SERVER_API_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    'http://localhost:8080';
  const url = new URL('/api/v1/competitions/worldcup/simulation', baseUrl);
  try {
    const response = await fetch(url.toString(), { next: { revalidate: 300 } });
    if (!response.ok) return null;
    return (await response.json()) as ApiSimulationResponse;
  } catch {
    return null;
  }
}

function toRow(entry: ApiSimulationLeaderboardEntry): ChampionLeaderboardRow {
  return {
    teamId: entry.team_id,
    team: entry.team_name_zh ?? entry.team_name,
    championProb: entry.champion_prob,
    runnerUpProb: entry.runner_up_prob,
    thirdProb: entry.third_prob,
    fourthProb: entry.fourth_prob,
    top4Prob: entry.top4_prob,
    qualifyProb: entry.qualify_prob,
  };
}

export default async function SimulationPage() {
  const sim = await fetchSimulation();
  const entries = sim?.results?.leaderboard ?? [];
  const rows = entries.map(toRow);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-slate-100">世界杯夺冠概率</h1>
      {rows.length === 0 ? (
        <Card>
          <CardBody className="text-center text-sm text-slate-400">
            暂无模拟数据。运行{' '}
            <code className="rounded bg-slate-800/70 px-1.5 py-0.5 text-xs">
              python -m scripts.run_tournament_simulation
            </code>{' '}
            生成一次。
          </CardBody>
        </Card>
      ) : (
        <ChampionLeaderboard
          rows={rows}
          trials={sim?.results?.trials ?? sim?.num_simulations ?? 0}
          modelVersion={sim?.model_version ?? 'unknown'}
          computedAt={sim?.computed_at ?? ''}
        />
      )}
    </div>
  );
}
