import type { Metadata } from 'next';

import { MarketBreakdown } from '@/components/track-record/MarketBreakdown';
import { PredictionHistory } from '@/components/track-record/PredictionHistory';
import { ROIChart, type RoiPoint } from '@/components/track-record/ROIChart';
import { StatsOverview } from '@/components/track-record/StatsOverview';
import { ShareButton } from '@/components/share/ShareButton';
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

export async function generateMetadata(): Promise<Metadata> {
  const overview = await fetchOverview();
  const roiPct =
    overview ? `${(overview.roi * 100).toFixed(1)}%` : '—';
  const hitPct =
    overview ? `${(overview.hitRate * 100).toFixed(1)}%` : '—';
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
  const overview = await fetchOverview();
  const byPeriod = await fetchByPeriod();

  // Phase 3.5: real cumulative-PnL series from the Java service. For now
  // we synthesise a flat line so the chart's dimensions stay correct.
  const series: RoiPoint[] = [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-900">战绩追踪</h1>
        <ShareButton
          targetType="track_record"
          targetUrl="/track-record"
        />
      </div>

      <StatsOverview overview={overview} />
      <ROIChart series={series} />
      <MarketBreakdown rows={byPeriod} />
      <PredictionHistory rows={[]} />
    </div>
  );
}
