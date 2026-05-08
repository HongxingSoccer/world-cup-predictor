import type { Metadata } from 'next';
import { cookies } from 'next/headers';

import { HeroIntro } from '@/components/home/HeroIntro';
import { HomeMatchTabs } from '@/components/match/HomeMatchTabs';
import { MatchDayHeader } from '@/components/match/MatchDayHeader';
import { PromotionBanner } from '@/components/subscription/PromotionBanner';
import { LOCALE_COOKIE } from '@/i18n/config';
import { ACCESS_COOKIE } from '@/lib/auth';
import type { MatchSummary } from '@/types';

// Force dynamic rendering so the root layout's per-request cookie read
// (locale) actually takes effect on the homepage. ISR was incompatible
// with cookie-driven i18n — the cached HTML always shipped the build-time
// locale regardless of the user's preference.
export const dynamic = 'force-dynamic';

const UPCOMING_DAYS = 60;

export function generateMetadata(): Metadata {
  const isEn = cookies().get(LOCALE_COOKIE)?.value === 'en';
  return isEn
    ? {
        title: 'World Cup 2026 AI Predictions',
        description:
          'AI match predictions with top picks and a public, cumulative track record.',
        openGraph: {
          title: 'World Cup 2026 AI Predictions',
          description:
            'Today’s AI predictions at a glance: win/draw/loss probability, top picks, scorelines.',
        },
      }
    : {
        title: 'World Cup 2026 AI 预测',
        description: 'AI 模型今日比赛预测，高价值推荐 + 公开累计战绩。',
        openGraph: {
          title: 'World Cup 2026 AI 预测',
          description: '今日 AI 预测一览：胜平负概率、高价值推荐、Top 比分。',
        },
      };
}

interface HomePageProps {
  searchParams: { date?: string };
}

async function fetchJson<T>(path: string): Promise<T | null> {
  const baseUrl =
    process.env.SERVER_API_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    'http://localhost:8080';
  const url = new URL(path, baseUrl);
  // Forward the access-token cookie so tier-gated fields (e.g.
  // `topSignalLevel`) reflect the logged-in user's plan instead of
  // collapsing to the anonymous defaults the Java tier ships.
  const access = cookies().get(ACCESS_COOKIE)?.value;
  const init: RequestInit = access
    ? { headers: { Authorization: `Bearer ${access}` }, cache: 'no-store' }
    : { next: { revalidate: 60 } };
  try {
    const response = await fetch(url.toString(), init);
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
      <HeroIntro />

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
