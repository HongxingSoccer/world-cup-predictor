'use client';

import { Heart } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';

import { CompactMatchCard, type CompactMatch } from '@/components/match/CompactMatchCard';
import { MatchListClient } from '@/components/match/MatchListClient';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Tabs, type TabItem } from '@/components/ui/Tabs';
import { useAuth } from '@/hooks/useAuth';
import { apiGet } from '@/lib/api';
import { toCompactMatches } from '@/lib/match-mappers';
import type { MatchSummary } from '@/types';

type TabId = 'today' | 'upcoming' | 'favorites';

interface HomeMatchTabsProps {
  today: MatchSummary[];
  upcoming: MatchSummary[];
  upcomingDays: number;
}

/**
 * Client-island that swaps the home page's match list between today /
 * upcoming / favorites. Today + upcoming come from SSR props (always
 * available); favorites are lazy-loaded only when authenticated and the
 * tab is selected. The favorites tab is hidden entirely for anonymous
 * users so the segmented control reads as just "今日 / 即将开赛".
 */
export function HomeMatchTabs({ today, upcoming, upcomingDays }: HomeMatchTabsProps) {
  const { isAuthenticated } = useAuth();
  const [tab, setTab] = useState<TabId>('today');
  const [favorites, setFavorites] = useState<CompactMatch[] | null>(null);
  const [favError, setFavError] = useState(false);

  const items = useMemo<ReadonlyArray<TabItem<TabId>>>(() => {
    const base: TabItem<TabId>[] = [
      { id: 'today', label: '今日比赛', count: today.length || null },
      { id: 'upcoming', label: '即将开赛', count: upcoming.length || null },
    ];
    if (isAuthenticated) {
      base.push({
        id: 'favorites',
        label: '我的收藏',
        count: favorites?.length ?? null,
      });
    }
    return base;
  }, [isAuthenticated, today.length, upcoming.length, favorites]);

  useEffect(() => {
    if (tab !== 'favorites' || favorites !== null || !isAuthenticated) return;
    let cancelled = false;
    (async () => {
      try {
        const raw = await apiGet<unknown>('/api/v1/users/me/favorites');
        if (cancelled) return;
        setFavorites(toCompactMatches(raw));
      } catch {
        if (cancelled) return;
        setFavError(true);
        setFavorites([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tab, favorites, isAuthenticated]);

  return (
    <div className="space-y-3">
      <Tabs value={tab} items={items} onChange={setTab} />

      {tab === 'today' ? (
        today.length === 0 ? (
          <EmptyState text="今日暂无可预测的比赛。" />
        ) : (
          <MatchListClient matches={today} />
        )
      ) : null}

      {tab === 'upcoming' ? (
        upcoming.length === 0 ? (
          <EmptyState text={`未来 ${upcomingDays} 天内暂无已生成预测的比赛。`} />
        ) : (
          <Card>
            <CardHeader>
              <h2 className="text-sm font-semibold text-slate-100">即将开赛</h2>
              <p className="text-xs text-slate-400">
                未来 {upcomingDays} 天内已生成预测的{' '}
                <span className="tabular-nums">{upcoming.length}</span> 场比赛
              </p>
            </CardHeader>
            <CardBody>
              <MatchListClient matches={upcoming} />
            </CardBody>
          </Card>
        )
      ) : null}

      {tab === 'favorites' ? <FavoritesPanel rows={favorites} error={favError} /> : null}
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <Card>
      <CardBody className="text-center text-sm text-slate-400">{text}</CardBody>
    </Card>
  );
}

function FavoritesPanel({
  rows,
  error,
}: {
  rows: CompactMatch[] | null;
  error: boolean;
}) {
  if (rows === null) {
    return (
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        <div className="h-20 animate-pulse rounded-xl bg-slate-800/60" />
        <div className="h-20 animate-pulse rounded-xl bg-slate-800/60" />
        <div className="h-20 animate-pulse rounded-xl bg-slate-800/60" />
      </div>
    );
  }
  if (error) {
    return (
      <Card>
        <CardBody className="text-center text-sm text-rose-400">
          收藏列表加载失败，请稍后刷新重试。
        </CardBody>
      </Card>
    );
  }
  if (rows.length === 0) {
    return (
      <Card>
        <CardBody className="flex flex-col items-center gap-2 py-8 text-center">
          <Heart size={28} className="text-rose-400/70" />
          <p className="text-sm text-slate-300">还没有收藏任何比赛</p>
          <p className="text-xs text-slate-500">
            进入比赛详情页点 ❤️，关注的比赛会在这里聚合显示。
          </p>
          <Link
            href="/worldcup/bracket"
            className="mt-2 text-xs text-cyan-300 underline-offset-4 hover:underline"
          >
            浏览淘汰赛 →
          </Link>
        </CardBody>
      </Card>
    );
  }
  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {rows.map((m) => (
        <CompactMatchCard key={m.matchId} match={m} />
      ))}
    </div>
  );
}
