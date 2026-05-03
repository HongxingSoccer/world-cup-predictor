import type { Metadata } from 'next';

import { MatchDayHeader } from '@/components/match/MatchDayHeader';
import { MatchListClient } from '@/components/match/MatchListClient';
import { PromotionBanner } from '@/components/subscription/PromotionBanner';
import { Card, CardBody } from '@/components/ui/Card';
import type { MatchSummary } from '@/types';

export const revalidate = 60; // ISR — refresh today's list every minute.

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

async function fetchMatchesForDate(date: string | undefined): Promise<MatchSummary[]> {
  const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8080';
  const url = new URL('/api/v1/matches/today', baseUrl);
  if (date) url.searchParams.set('date', date);
  try {
    const response = await fetch(url.toString(), { next: { revalidate: 60 } });
    if (!response.ok) return [];
    return (await response.json()) as MatchSummary[];
  } catch {
    return [];
  }
}

export default async function HomePage({ searchParams }: HomePageProps) {
  const matches = await fetchMatchesForDate(searchParams.date);

  return (
    <div className="space-y-4">
      <MatchDayHeader date={searchParams.date} />

      {matches.length === 0 ? (
        <Card>
          <CardBody className="text-center text-sm text-slate-500">
            今日暂无可预测的比赛。
          </CardBody>
        </Card>
      ) : (
        <MatchListClient matches={matches} />
      )}

      <PromotionBanner />
    </div>
  );
}
