import type { Metadata } from 'next';
import Link from 'next/link';

import { Card, CardBody, CardHeader } from '@/components/ui/Card';

export const metadata: Metadata = {
  title: '球队夺冠路径',
  description: '一支球队在 2026 世界杯各阶段的晋级概率。',
};

export const dynamic = 'force-dynamic';

interface TeamPathPayload {
  team_id: number;
  team_name: string;
  team_name_zh: string | null;
  qualify_first_prob: number;
  qualify_second_prob: number;
  qualify_prob: number;
  round_of_16_prob: number;
  quarterfinal_prob: number;
  semifinal_prob: number;
  final_prob: number;
  champion_prob: number;
  runner_up_prob: number;
  third_prob: number;
  fourth_prob: number;
  top4_prob: number;
  expected_points: number;
  expected_gd: number;
}

interface TeamPathResponse {
  team_id?: number;
  simulation_id?: number;
  simulation_version?: string;
  computed_at?: string;
  path?: TeamPathPayload;
}

async function fetchTeamPath(teamId: string): Promise<TeamPathResponse | null> {
  const baseUrl =
    process.env.SERVER_API_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    'http://localhost:8080';
  const url = new URL(`/api/v1/competitions/worldcup/team/${teamId}/path`, baseUrl);
  try {
    const response = await fetch(url.toString(), { next: { revalidate: 300 } });
    if (!response.ok) return null;
    const body = (await response.json()) as TeamPathResponse;
    if (!body.path) return null;
    return body;
  } catch {
    return null;
  }
}

const STAGES: Array<{ label: string; key: keyof TeamPathPayload; accent: string }> = [
  { label: '小组赛出线', key: 'qualify_prob', accent: 'bg-sky-500' },
  { label: '16 强', key: 'round_of_16_prob', accent: 'bg-sky-500' },
  { label: '8 强', key: 'quarterfinal_prob', accent: 'bg-sky-500' },
  { label: '4 强 / 半决赛', key: 'semifinal_prob', accent: 'bg-emerald-500' },
  { label: '决赛', key: 'final_prob', accent: 'bg-amber-500' },
  { label: '冠军', key: 'champion_prob', accent: 'bg-amber-600' },
];

const PODIUM: Array<{ label: string; key: keyof TeamPathPayload }> = [
  { label: '冠军', key: 'champion_prob' },
  { label: '亚军', key: 'runner_up_prob' },
  { label: '季军', key: 'third_prob' },
  { label: '殿军', key: 'fourth_prob' },
];

function pct(value: number): string {
  return `${(value * 100).toFixed(2)}%`;
}

export default async function TeamPathPage({
  params,
}: {
  params: { teamId: string };
}) {
  const data = await fetchTeamPath(params.teamId);
  if (!data || !data.path) {
    return (
      <div className="space-y-4">
        <Link href="/worldcup/simulation" className="text-sm text-brand-600 hover:underline">
          ← 返回夺冠概率榜
        </Link>
        <Card>
          <CardBody className="text-center text-sm text-slate-500">
            该球队尚未出现在最近一次模拟中。
          </CardBody>
        </Card>
      </div>
    );
  }

  const path = data.path;
  const teamName = path.team_name_zh ?? path.team_name;

  return (
    <div className="space-y-4">
      <Link href="/worldcup/simulation" className="text-sm text-brand-600 hover:underline">
        ← 返回夺冠概率榜
      </Link>
      <Card>
        <CardHeader>
          <h1 className="text-xl font-bold text-slate-900">{teamName}</h1>
          <p className="text-xs text-slate-500">
            模拟 #{data.simulation_id} · {data.simulation_version} · 计算于{' '}
            {data.computed_at
              ? new Date(data.computed_at).toLocaleString('zh-CN', { hour12: false })
              : '—'}
          </p>
        </CardHeader>
        <CardBody className="space-y-6">
          {/* 各阶段晋级概率 */}
          <div className="space-y-2">
            <h2 className="text-sm font-semibold text-slate-700">各阶段晋级概率</h2>
            <div className="space-y-2">
              {STAGES.map((stage) => {
                const value = path[stage.key] as number;
                const width = Math.min(100, value * 100);
                return (
                  <div key={stage.key} className="flex items-center gap-3">
                    <span className="w-24 text-sm text-slate-700">{stage.label}</span>
                    <div className="h-2 flex-1 rounded-full bg-slate-100">
                      <div
                        className={`h-full rounded-full ${stage.accent}`}
                        style={{ width: `${width}%` }}
                      />
                    </div>
                    <span className="w-20 text-right text-sm tabular-nums text-slate-700">
                      {pct(value)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* 决赛阶段名次 */}
          <div className="space-y-2">
            <h2 className="text-sm font-semibold text-slate-700">最终名次概率</h2>
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
              {PODIUM.map((pod) => (
                <div key={pod.key} className="rounded-lg border border-slate-200 p-3">
                  <div className="text-xs text-slate-500">{pod.label}</div>
                  <div className="text-lg font-bold text-slate-900 tabular-nums">
                    {pct(path[pod.key] as number)}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 小组赛预期 */}
          <div className="space-y-2">
            <h2 className="text-sm font-semibold text-slate-700">小组赛预期</h2>
            <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
              <div className="rounded-lg border border-slate-200 p-3">
                <div className="text-xs text-slate-500">小组第一</div>
                <div className="text-lg font-bold text-slate-900 tabular-nums">
                  {pct(path.qualify_first_prob)}
                </div>
              </div>
              <div className="rounded-lg border border-slate-200 p-3">
                <div className="text-xs text-slate-500">小组第二</div>
                <div className="text-lg font-bold text-slate-900 tabular-nums">
                  {pct(path.qualify_second_prob)}
                </div>
              </div>
              <div className="rounded-lg border border-slate-200 p-3">
                <div className="text-xs text-slate-500">期望积分</div>
                <div className="text-lg font-bold text-slate-900 tabular-nums">
                  {path.expected_points.toFixed(2)}
                </div>
              </div>
              <div className="rounded-lg border border-slate-200 p-3">
                <div className="text-xs text-slate-500">期望净胜球</div>
                <div className="text-lg font-bold text-slate-900 tabular-nums">
                  {path.expected_gd >= 0 ? '+' : ''}
                  {path.expected_gd.toFixed(2)}
                </div>
              </div>
            </div>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
