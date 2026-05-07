import type { Metadata } from 'next';

import { Card, CardBody } from '@/components/ui/Card';
import { GroupStandings, type GroupStandingRow } from '@/components/worldcup/GroupStandings';

export const metadata: Metadata = {
  title: '世界杯小组赛积分榜',
  description: '2026 世界杯各小组的实时积分榜与净胜球。',
};

// Render on every request — the standings change each match, and the SSR
// fetch needs the docker-only SERVER_API_URL which is not available at
// build time.
export const dynamic = 'force-dynamic';

interface ApiStandingsRow {
  position: number;
  team_name: string;
  team_name_zh: string | null;
  played: number;
  wins: number;
  draws: number;
  losses: number;
  goals_for: number;
  goals_against: number;
  goal_diff: number;
  points: number;
}

interface ApiStandingsGroup {
  name: string;
  rows: ApiStandingsRow[];
}

interface ApiStandingsResponse {
  competition: string;
  year: number;
  groups: ApiStandingsGroup[];
}

async function fetchStandings(): Promise<ApiStandingsGroup[]> {
  const baseUrl =
    process.env.SERVER_API_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    'http://localhost:8080';
  const url = new URL('/api/v1/competitions/worldcup/standings', baseUrl);
  try {
    const response = await fetch(url.toString(), { next: { revalidate: 120 } });
    if (!response.ok) return [];
    const body = (await response.json()) as ApiStandingsResponse;
    return body.groups ?? [];
  } catch {
    return [];
  }
}

function toRow(row: ApiStandingsRow): GroupStandingRow {
  return {
    position: row.position,
    team: row.team_name_zh ?? row.team_name,
    played: row.played,
    wins: row.wins,
    draws: row.draws,
    losses: row.losses,
    goalsFor: row.goals_for,
    goalsAgainst: row.goals_against,
    goalDiff: row.goal_diff,
    points: row.points,
  };
}

export default async function GroupsPage() {
  const groups = await fetchStandings();

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-slate-100">世界杯小组赛</h1>
      {groups.length === 0 ? (
        <Card>
          <CardBody className="text-center text-sm text-slate-400">
            暂无小组赛数据，等待赛程录入。
          </CardBody>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {groups.map((group) => (
            <GroupStandings
              key={group.name}
              groupName={group.name}
              rows={group.rows.map(toRow)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
