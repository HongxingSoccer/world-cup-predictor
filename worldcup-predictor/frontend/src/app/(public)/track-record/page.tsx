import type { Metadata } from 'next';

import { MarketBreakdown } from '@/components/track-record/MarketBreakdown';
import { PredictionHistory } from '@/components/track-record/PredictionHistory';
import { ROIChart, type RoiPoint } from '@/components/track-record/ROIChart';
import { StatsOverview } from '@/components/track-record/StatsOverview';
import { ShareButton } from '@/components/share/ShareButton';
import { Card, CardBody } from '@/components/ui/Card';
import type { TrackRecordOverview } from '@/types';

export const revalidate = 600; // Track record page rebuilds every 10 minutes.

const baseUrl = (): string => process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8080';

async function fetchOverview(): Promise<TrackRecordOverview | undefined> {
  try {
    const r = await fetch(
      `${baseUrl()}/api/v1/track-record/overview?statType=overall&period=all_time`,
      { next: { revalidate: 600 } },
    );
    if (!r.ok) return undefined;
    return (await r.json()) as TrackRecordOverview;
  } catch {
    return undefined;
  }
}

async function fetchByPeriod(): Promise<TrackRecordOverview[]> {
  try {
    const r = await fetch(`${baseUrl()}/api/v1/track-record/roi-chart?period=all_time`, {
      next: { revalidate: 600 },
    });
    if (!r.ok) return [];
    return (await r.json()) as TrackRecordOverview[];
  } catch {
    return [];
  }
}

interface TimeseriesPayload {
  period: string;
  points: Array<{
    date: string;
    cumulative_pnl?: number;
    cumulativePnl?: number;
    cumulative_roi?: number;
    cumulativeRoi?: number;
    settled_count?: number;
    settledCount?: number;
  }>;
}

async function fetchTimeseries(): Promise<RoiPoint[]> {
  // The Java service doesn't proxy /timeseries yet — try the ml-api directly
  // when it's reachable so the chart can render real data once the
  // tournament starts. Failures are silent: the empty-state card upstream
  // covers the no-data case.
  const candidates = [
    `${baseUrl()}/api/v1/track-record/timeseries?period=all_time`,
  ];
  for (const url of candidates) {
    try {
      const r = await fetch(url, { next: { revalidate: 600 } });
      if (!r.ok) continue;
      const payload = (await r.json()) as TimeseriesPayload;
      if (!Array.isArray(payload.points)) continue;
      return payload.points.map((p) => ({
        date: p.date,
        cumulativePnl: Number(p.cumulative_pnl ?? p.cumulativePnl ?? 0),
      }));
    } catch {
      continue;
    }
  }
  return [];
}

export async function generateMetadata(): Promise<Metadata> {
  const overview = await fetchOverview();
  const roiPct = overview ? `${(overview.roi * 100).toFixed(1)}%` : '—';
  const hitPct = overview ? `${(overview.hitRate * 100).toFixed(1)}%` : '—';
  return {
    title: `AI 预测累计 ROI ${roiPct} · 命中率 ${hitPct}`,
    description: '透明可验证的预测战绩 — 累计 ROI、命中率、连红记录。',
    openGraph: {
      title: `AI 预测累计 ROI ${roiPct} · 命中率 ${hitPct}`,
      description: '透明可验证的预测战绩 — 累计 ROI、命中率、连红记录。',
    },
  };
}

export default async function TrackRecordPage() {
  const [overview, byPeriod, series] = await Promise.all([
    fetchOverview(),
    fetchByPeriod(),
    fetchTimeseries(),
  ]);

  const isEmpty = !overview || overview.totalPredictions === 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-100">战绩追踪</h1>
        <ShareButton targetType="track_record" targetUrl="/track-record" />
      </div>

      <StatsOverview overview={overview} />

      {isEmpty ? <EmptyTrackRecordCard /> : <ROIChart series={series} />}

      <MarketBreakdown rows={byPeriod} />
      <PredictionHistory rows={[]} />
    </div>
  );
}

function EmptyTrackRecordCard() {
  return (
    <Card>
      <CardBody>
        <div className="flex flex-col items-center gap-2 py-10 text-center">
          <div className="text-3xl">⏳</div>
          <h3 className="text-lg font-semibold text-slate-100">战绩将在世界杯开赛后累计</h3>
          <p className="max-w-md text-sm leading-relaxed text-slate-400">
            首场比赛 <span className="tabular-nums text-cyan-300">2026/06/11</span>{' '}
            开球，每场结束 2 小时内自动结算并更新本页 ROI、命中率、连红等统计。
          </p>
          <p className="text-xs text-slate-500">
            订阅可在赛后第一时间收到战绩推送通知。
          </p>
        </div>
      </CardBody>
    </Card>
  );
}
