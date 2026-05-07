import { Card, CardBody, CardHeader } from '@/components/ui/Card';

export interface GroupStandingRow {
  position: number;
  team: string;
  played: number;
  wins: number;
  draws: number;
  losses: number;
  goalsFor: number;
  goalsAgainst: number;
  goalDiff: number;
  points: number;
}

interface GroupStandingsProps {
  groupName: string;
  rows: GroupStandingRow[];
}

export function GroupStandings({ groupName, rows }: GroupStandingsProps) {
  return (
    <Card>
      <CardHeader>
        <h3 className="text-sm font-semibold text-slate-100">小组 {groupName}</h3>
      </CardHeader>
      <CardBody className="overflow-x-auto p-0">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-900/50 text-xs uppercase tracking-wider text-slate-400">
            <tr>
              <th className="px-3 py-2 text-left">#</th>
              <th className="px-3 py-2 text-left">球队</th>
              <th className="px-2 py-2 text-right">赛</th>
              <th className="px-2 py-2 text-right">胜</th>
              <th className="px-2 py-2 text-right">平</th>
              <th className="px-2 py-2 text-right">负</th>
              <th className="px-2 py-2 text-right">进</th>
              <th className="px-2 py-2 text-right">失</th>
              <th className="px-2 py-2 text-right">净</th>
              <th className="px-3 py-2 text-right font-bold">分</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.team} className="border-t border-slate-800/70">
                <td className="px-3 py-2 text-slate-400">{row.position}</td>
                <td className="px-3 py-2 font-medium text-slate-100">{row.team}</td>
                <td className="px-2 py-2 text-right tabular-nums">{row.played}</td>
                <td className="px-2 py-2 text-right tabular-nums">{row.wins}</td>
                <td className="px-2 py-2 text-right tabular-nums">{row.draws}</td>
                <td className="px-2 py-2 text-right tabular-nums">{row.losses}</td>
                <td className="px-2 py-2 text-right tabular-nums">{row.goalsFor}</td>
                <td className="px-2 py-2 text-right tabular-nums">{row.goalsAgainst}</td>
                <td className="px-2 py-2 text-right tabular-nums">{row.goalDiff}</td>
                <td className="px-3 py-2 text-right font-bold tabular-nums">{row.points}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardBody>
    </Card>
  );
}
