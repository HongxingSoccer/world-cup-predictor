'use client';

import { Heart } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';

import { CompactMatchCard, type CompactMatch } from '@/components/match/CompactMatchCard';
import { MatchListClient } from '@/components/match/MatchListClient';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { Tabs, type TabItem } from '@/components/ui/Tabs';
import { useT } from '@/i18n/I18nProvider';
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

export function HomeMatchTabs({ today, upcoming, upcomingDays }: HomeMatchTabsProps) {
  const t = useT();
  const { isAuthenticated } = useAuth();
  const [tab, setTab] = useState<TabId>('today');
  const [favorites, setFavorites] = useState<CompactMatch[] | null>(null);
  const [favError, setFavError] = useState(false);

  const items = useMemo<ReadonlyArray<TabItem<TabId>>>(() => {
    const base: TabItem<TabId>[] = [
      { id: 'today', label: t('match.today'), count: today.length || null },
      { id: 'upcoming', label: t('match.upcoming'), count: upcoming.length || null },
    ];
    if (isAuthenticated) {
      base.push({
        id: 'favorites',
        label: t('match.myFavorites'),
        count: favorites?.length ?? null,
      });
    }
    return base;
  }, [isAuthenticated, today.length, upcoming.length, favorites, t]);

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
          <EmptyState text={t('match.noTodayMatches')} />
        ) : (
          <MatchListClient matches={today} />
        )
      ) : null}

      {tab === 'upcoming' ? (
        upcoming.length === 0 ? (
          <EmptyState
            text={t('match.noUpcomingMatches').replace('{days}', String(upcomingDays))}
          />
        ) : (
          <Card>
            <CardHeader>
              <h2 className="text-sm font-semibold text-slate-100">{t('match.upcoming')}</h2>
              <p className="text-xs text-slate-400">
                {t('match.upcomingDescription')
                  .replace('{count}', String(upcoming.length))
                  .replace('{days}', String(upcomingDays))}
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
  const t = useT();
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
          {t('match.myFavoritesError')}
        </CardBody>
      </Card>
    );
  }
  if (rows.length === 0) {
    return (
      <Card>
        <CardBody className="flex flex-col items-center gap-2 py-8 text-center">
          <Heart size={28} className="text-rose-400/70" />
          <p className="text-sm text-slate-300">{t('match.myFavoritesEmpty')}</p>
          <Link
            href="/worldcup/bracket"
            className="mt-2 text-xs text-cyan-300 underline-offset-4 hover:underline"
          >
            {t('match.browseKnockout')}
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
