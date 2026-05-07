import Link from 'next/link';

import { Card, CardBody, CardHeader } from '@/components/ui/Card';

export interface ChampionLeaderboardRow {
  teamId: number;
  team: string;
  championProb: number;
  runnerUpProb: number;
  thirdProb: number;
  fourthProb: number;
  top4Prob: number;
  qualifyProb: number;
}

interface ChampionLeaderboardProps {
  rows: ChampionLeaderboardRow[];
  trials: number;
  modelVersion: string;
  computedAt: string;
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

// Render a horizontal bar whose width is proportional to `value` against the
// row's max — keeps the visual ranking obvious without forcing absolute scale.
function Bar({ value, max, accent }: { value: number; max: number; accent: string }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-14 rounded-full bg-slate-800/70">
        <div className={`h-full rounded-full ${accent}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-12 text-right tabular-nums text-slate-300">{formatPercent(value)}</span>
    </div>
  );
}

export function ChampionLeaderboard({
  rows,
  trials,
  modelVersion,
  computedAt,
}: ChampionLeaderboardProps) {
  const maxChamp = rows.reduce((m, r) => Math.max(m, r.championProb), 0);
  const maxTop4 = rows.reduce((m, r) => Math.max(m, r.top4Prob), 0);
  const maxQual = rows.reduce((m, r) => Math.max(m, r.qualifyProb), 0);

  return (
    <Card>
      <CardHeader className="flex flex-col gap-1">
        <h3 className="text-sm font-semibold text-slate-100">夺冠概率榜</h3>
        <p className="text-xs text-slate-400">
          基于 {trials.toLocaleString()} 次蒙特卡洛模拟 · 模型 {modelVersion} · 计算于{' '}
          {new Date(computedAt).toLocaleString('zh-CN', { hour12: false })}
        </p>
      </CardHeader>
      <CardBody className="overflow-x-auto p-0">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-900/50 text-xs uppercase tracking-wider text-slate-400">
            <tr>
              <th className="px-3 py-2 text-left">#</th>
              <th className="px-3 py-2 text-left">球队</th>
              <th className="px-3 py-2 text-right">夺冠</th>
              <th className="px-3 py-2 text-right">进四强</th>
              <th className="px-3 py-2 text-right">出线</th>
              <th className="px-3 py-2 text-right text-slate-400">亚军</th>
              <th className="px-3 py-2 text-right text-slate-400">季军</th>
              <th className="px-3 py-2 text-right text-slate-400">殿军</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => (
              <tr
                key={row.teamId}
                className="border-t border-slate-800/70 hover:bg-slate-900/50"
              >
                <td className="px-3 py-2 text-slate-400">{idx + 1}</td>
                <td className="px-3 py-2 font-medium text-slate-100">
                  <Link
                    href={`/worldcup/team/${row.teamId}`}
                    className="hover:text-brand-600 hover:underline"
                  >
                    {row.team}
                  </Link>
                </td>
                <td className="px-3 py-2 text-right">
                  <Bar value={row.championProb} max={maxChamp} accent="bg-amber-500" />
                </td>
                <td className="px-3 py-2 text-right">
                  <Bar value={row.top4Prob} max={maxTop4} accent="bg-emerald-500" />
                </td>
                <td className="px-3 py-2 text-right">
                  <Bar value={row.qualifyProb} max={maxQual} accent="bg-sky-500" />
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-slate-400">
                  {formatPercent(row.runnerUpProb)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-slate-400">
                  {formatPercent(row.thirdProb)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-slate-400">
                  {formatPercent(row.fourthProb)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardBody>
    </Card>
  );
}
