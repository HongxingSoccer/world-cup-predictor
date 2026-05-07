'use client';

import { Heart } from 'lucide-react';
import { useEffect, useState } from 'react';

import { CompactMatchCard, type CompactMatch } from '@/components/match/CompactMatchCard';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { apiGet } from '@/lib/api';
import { toCompactMatches } from '@/lib/match-mappers';

/**
 * Authenticated fetch for the current user's favourite matches. Renders the
 * loading shimmer / empty hint / grid in-place — the parent profile page just
 * drops it into the layout.
 */
export function MyFavoritesCard() {
  const [matches, setMatches] = useState<CompactMatch[]>([]);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const raw = await apiGet<unknown>('/api/v1/users/me/favorites');
        if (cancelled) return;
        setMatches(toCompactMatches(raw));
        setState('ready');
      } catch {
        if (cancelled) return;
        setState('error');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center gap-2">
          <Heart size={16} className="text-rose-400" />
          <h2 className="text-base font-semibold text-slate-100">我的收藏</h2>
        </div>
        {state === 'ready' && matches.length > 0 ? (
          <span className="text-xs tabular-nums text-slate-400">
            {matches.length} 场
          </span>
        ) : null}
      </CardHeader>
      <CardBody>
        {state === 'loading' ? (
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="h-20 animate-pulse rounded-xl bg-slate-800/60" />
            <div className="h-20 animate-pulse rounded-xl bg-slate-800/60" />
          </div>
        ) : state === 'error' ? (
          <div className="py-4 text-sm text-rose-400">
            收藏列表加载失败，请稍后刷新重试。
          </div>
        ) : matches.length === 0 ? (
          <div className="py-6 text-center text-sm text-slate-400">
            还没有收藏任何比赛 — 在比赛详情页点 ❤️ 即可加入。
          </div>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2">
            {matches.map((m) => (
              <CompactMatchCard key={m.matchId} match={m} />
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
}
