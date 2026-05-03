import type { Metadata } from 'next';

import { GroupStandings, type GroupStandingRow } from '@/components/worldcup/GroupStandings';

export const metadata: Metadata = {
  title: '世界杯小组赛积分榜',
  description: '2026 世界杯 8 个小组的实时积分榜与净胜球。',
};

// Phase 3.5: pull live data from /api/v1/competitions/worldcup/standings.
// For the MVP we render placeholder groups so the layout is reviewable end-to-end.
const PLACEHOLDER_GROUPS: { name: string; rows: GroupStandingRow[] }[] = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'].map(
  (name) => ({
    name,
    rows: ['Team 1', 'Team 2', 'Team 3', 'Team 4'].map((team, idx) => ({
      position: idx + 1,
      team: `${name} · ${team}`,
      played: 0,
      wins: 0,
      draws: 0,
      losses: 0,
      goalsFor: 0,
      goalsAgainst: 0,
      goalDiff: 0,
      points: 0,
    })),
  }),
);

export default function GroupsPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-slate-900">世界杯小组赛</h1>
      <div className="grid gap-4 md:grid-cols-2">
        {PLACEHOLDER_GROUPS.map((group) => (
          <GroupStandings key={group.name} groupName={group.name} rows={group.rows} />
        ))}
      </div>
    </div>
  );
}
