import type { Metadata } from 'next';

import { HomeMatchTabs } from '@/components/match/HomeMatchTabs';
import { MatchDayHeader } from '@/components/match/MatchDayHeader';
import { PromotionBanner } from '@/components/subscription/PromotionBanner';
import type { MatchSummary } from '@/types';

export const revalidate = 60; // ISR — refresh today's list every minute.

const UPCOMING_DAYS = 60;

export const metadata: Metadata = {
  title: 'World Cup 2026 AI 预测',
  description: 'AI 模型今日比赛预测、价值信号 + 累计 ROI 战绩。',
  openGraph: {
    title: 'World Cup 2026 AI 预测',
    description: '今日 AI 预测一览：胜平负概率、价值信号、Top 比分。',
  },
};

interface HomePageProps {
  searchParams: { date?: string };
}

async function fetchJson<T>(path: string): Promise<T | null> {
  const baseUrl =
    process.env.SERVER_API_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    'http://localhost:8080';
  const url = new URL(path, baseUrl);
  try {
    const response = await fetch(url.toString(), { next: { revalidate: 60 } });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

async function fetchMatchesForDate(date: string | undefined): Promise<MatchSummary[]> {
  const path = date ? `/api/v1/matches/today?date=${date}` : '/api/v1/matches/today';
  return (await fetchJson<MatchSummary[]>(path)) ?? [];
}

async function fetchUpcoming(days: number): Promise<MatchSummary[]> {
  return (await fetchJson<MatchSummary[]>(`/api/v1/matches/upcoming?days=${days}`)) ?? [];
}

export default async function HomePage({ searchParams }: HomePageProps) {
  // Fetch in parallel — they're independent and both hit the same Java tier.
  const [matches, upcoming] = await Promise.all([
    fetchMatchesForDate(searchParams.date),
    fetchUpcoming(UPCOMING_DAYS),
  ]);

  return (
    <div className="space-y-4">
      <MatchDayHeader date={searchParams.date} />

      <HomeMatchTabs
        today={matches}
        upcoming={upcoming}
        upcomingDays={UPCOMING_DAYS}
      />

      <PromotionBanner />
    </div>
  );
}
