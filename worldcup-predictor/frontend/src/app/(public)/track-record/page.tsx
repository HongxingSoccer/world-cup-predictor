import type { Metadata } from 'next';

import { MarketBreakdown } from '@/components/track-record/MarketBreakdown';
import {
  PredictionHistory,
  type PredictionHistoryRow,
} from '@/components/track-record/PredictionHistory';
import { ROIChart, type RoiPoint } from '@/components/track-record/ROIChart';
import { StatsOverview } from '@/components/track-record/StatsOverview';
import {
  EmptyTrackRecordCard,
  TrackRecordHeader,
} from '@/components/track-record/TrackRecordHeader';
import type { TrackRecordOverview } from '@/types';

export const revalidate = 600; // Track record page rebuilds every 10 minutes.

// SSR fetches inside docker need to reach java-api over the docker network;
// SERVER_API_URL is set in docker-compose for that path. Browser bundles fall
// through to NEXT_PUBLIC_API_URL.
const baseUrl = (): string =>
  process.env.SERVER_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  'http://localhost:8080';

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
  try {
    const r = await fetch(`${baseUrl()}/api/v1/track-record/timeseries?period=all_time`, {
      next: { revalidate: 600 },
    });
    if (!r.ok) return [];
    const payload = (await r.json()) as TimeseriesPayload;
    if (!Array.isArray(payload.points)) return [];
    return payload.points.map((p) => ({
      date: p.date,
      cumulativePnl: Number(p.cumulative_pnl ?? p.cumulativePnl ?? 0),
    }));
  } catch {
    return [];
  }
}

interface HistoryPayload {
  total: number;
  items: Array<{
    matchId?: number;
    match_id?: number;
    matchDate?: string;
    match_date?: string;
    homeTeam?: string;
    home_team?: string;
    awayTeam?: string;
    away_team?: string;
    predicted: 'H' | 'D' | 'A';
    actual: 'H' | 'D' | 'A';
    hit: boolean;
    pnlUnit?: number;
    pnl_unit?: number;
  }>;
}

async function fetchHistory(): Promise<PredictionHistoryRow[]> {
  try {
    const r = await fetch(`${baseUrl()}/api/v1/track-record/history?size=20&page=0`, {
      next: { revalidate: 600 },
    });
    if (!r.ok) return [];
    const payload = (await r.json()) as HistoryPayload;
    if (!Array.isArray(payload.items)) return [];
    return payload.items.map((item) => ({
      matchId: Number(item.matchId ?? item.match_id ?? 0),
      matchDate: String(item.matchDate ?? item.match_date ?? ''),
      homeTeam: String(item.homeTeam ?? item.home_team ?? ''),
      awayTeam: String(item.awayTeam ?? item.away_team ?? ''),
      predicted: item.predicted,
      actual: item.actual,
      hit: Boolean(item.hit),
      pnlUnit: Number(item.pnlUnit ?? item.pnl_unit ?? 0),
    }));
  } catch {
    return [];
  }
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
  const [overview, byPeriod, series, history] = await Promise.all([
    fetchOverview(),
    fetchByPeriod(),
    fetchTimeseries(),
    fetchHistory(),
  ]);

  const isEmpty = !overview || overview.totalPredictions === 0;

  return (
    <div className="space-y-4">
      <TrackRecordHeader />

      <StatsOverview overview={overview} />

      {isEmpty ? <EmptyTrackRecordCard /> : <ROIChart series={series} />}

      <MarketBreakdown rows={byPeriod} />
      <PredictionHistory rows={history} />
    </div>
  );
}
