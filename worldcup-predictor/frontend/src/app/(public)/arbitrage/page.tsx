'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { ArbOpportunityCard } from '@/components/arbitrage/ArbOpportunityCard';
import { WatchlistPanel } from '@/components/arbitrage/WatchlistPanel';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { useAuth } from '@/hooks/useAuth';
import { useSubscription } from '@/hooks/useSubscription';
import { useT } from '@/i18n/I18nProvider';
import { listOpportunities } from '@/lib/arbitrageApi';
import { cn } from '@/lib/utils';
import type { ArbOpportunity } from '@/types/arbitrage';

const MARKET_FILTERS: Array<{ value: '' | string; key: string }> = [
  { value: '', key: 'positions.filterAll' },
  { value: '1x2', key: 'positions.market.1x2' },
  { value: 'over_under', key: 'positions.market.over_under' },
  { value: 'asian_handicap', key: 'positions.market.asian_handicap' },
  { value: 'btts', key: 'positions.market.btts' },
];

export default function ArbitragePage() {
  const t = useT();
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const { tier } = useSubscription();
  const [opps, setOpps] = useState<ArbOpportunity[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [marketFilter, setMarketFilter] = useState('');
  const [showWatchlist, setShowWatchlist] = useState(false);

  useEffect(() => {
    if (typeof window !== 'undefined' && !isAuthenticated) {
      router.replace('/login?next=/arbitrage');
    }
  }, [isAuthenticated, router]);

  const tierLocked = isAuthenticated && tier === 'free';

  useEffect(() => {
    if (!isAuthenticated || tierLocked) return;
    let cancelled = false;
    setOpps(null);
    setError(null);
    (async () => {
      try {
        const rows = await listOpportunities(marketFilter || undefined);
        if (cancelled) return;
        setOpps(rows);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : t('arbitrage.loadFailed'));
        setOpps([]);
      }
    })();
    // Poll every 60s so the list reflects fresh scanner output.
    const id = window.setInterval(() => {
      (async () => {
        try {
          const rows = await listOpportunities(marketFilter || undefined);
          if (!cancelled) setOpps(rows);
        } catch {
          /* noop */
        }
      })();
    }, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [marketFilter, isAuthenticated, tierLocked, t]);

  if (!isAuthenticated) {
    return null;
  }

  if (tierLocked) {
    return (
      <div className="space-y-3">
        <h1 className="text-xl font-bold text-slate-100">{t('arbitrage.title')}</h1>
        <Card>
          <CardBody className="space-y-3 text-sm text-slate-300">
            <p>{t('arbitrage.tierLocked')}</p>
            <Button onClick={() => router.push('/subscribe')}>{t('nav.subscribe')}</Button>
          </CardBody>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h1 className="text-xl font-bold text-slate-100">{t('arbitrage.title')}</h1>
          <p className="mt-1 text-xs text-slate-400">{t('arbitrage.subtitle')}</p>
        </div>
        <Button variant="ghost" onClick={() => setShowWatchlist((v) => !v)}>
          {showWatchlist ? t('arbitrage.hideWatchlist') : t('arbitrage.showWatchlist')}
        </Button>
      </div>

      {showWatchlist ? (
        <Card>
          <CardHeader>
            <h2 className="text-sm font-semibold text-slate-100">{t('arbitrage.watchlist.title')}</h2>
            <span className="text-xs text-slate-400">{t('arbitrage.watchlist.subtitle')}</span>
          </CardHeader>
          <CardBody>
            <WatchlistPanel />
          </CardBody>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center gap-2">
            {MARKET_FILTERS.map((opt) => (
              <button
                key={opt.value || 'all'}
                type="button"
                onClick={() => setMarketFilter(opt.value)}
                className={cn(
                  'rounded-full px-3 py-1 text-xs font-semibold transition-colors',
                  marketFilter === opt.value
                    ? 'bg-cyan-500/20 text-cyan-200'
                    : 'bg-slate-800/60 text-slate-400 hover:bg-slate-800',
                )}
              >
                {t(opt.key)}
              </button>
            ))}
          </div>
        </CardHeader>
        <CardBody className="space-y-2">
          {error ? <p className="text-xs text-rose-400">{error}</p> : null}
          {opps === null ? (
            <div className="space-y-2">
              <div className="h-28 animate-pulse rounded-xl bg-slate-800/60" />
              <div className="h-28 animate-pulse rounded-xl bg-slate-800/60" />
            </div>
          ) : opps.length === 0 ? (
            <p className="py-12 text-center text-sm text-slate-400">{t('arbitrage.empty')}</p>
          ) : (
            opps.map((opp) => <ArbOpportunityCard key={opp.id} opportunity={opp} />)
          )}
        </CardBody>
      </Card>
    </div>
  );
}
