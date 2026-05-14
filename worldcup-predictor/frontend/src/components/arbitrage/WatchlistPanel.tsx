'use client';

import { Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { useT } from '@/i18n/I18nProvider';
import {
  createWatchlist,
  deleteWatchlist,
  listWatchlist,
} from '@/lib/arbitrageApi';
import { cn } from '@/lib/utils';
import type { WatchlistEntry } from '@/types/arbitrage';

const ALL_MARKETS = ['1x2', 'over_under', 'asian_handicap', 'btts'];

export function WatchlistPanel() {
  const t = useT();
  const [rules, setRules] = useState<WatchlistEntry[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [minMargin, setMinMargin] = useState('0.02');
  const [selectedMarkets, setSelectedMarkets] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const refresh = async () => {
    try {
      const rows = await listWatchlist();
      setRules(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('arbitrage.watchlist.loadFailed'));
      setRules([]);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const toggleMarket = (m: string) =>
    setSelectedMarkets((prev) => (prev.includes(m) ? prev.filter((x) => x !== m) : [...prev, m]));

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const margin = Number.parseFloat(minMargin);
      if (!Number.isFinite(margin) || margin < 0) {
        setError(t('arbitrage.watchlist.errorMargin'));
        return;
      }
      await createWatchlist({
        marketTypes: selectedMarkets.length === 0 ? null : selectedMarkets,
        minProfitMargin: margin,
        notifyEnabled: true,
      });
      setMinMargin('0.02');
      setSelectedMarkets([]);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : t('arbitrage.watchlist.createFailed'));
    } finally {
      setSubmitting(false);
    }
  };

  const remove = async (id: number) => {
    try {
      await deleteWatchlist(id);
      setRules((prev) => prev?.filter((r) => r.id !== id) ?? null);
    } catch {
      setError(t('arbitrage.watchlist.deleteFailed'));
    }
  };

  return (
    <div className="space-y-3">
      <form onSubmit={submit} className="space-y-2 rounded-xl border border-slate-800/70 bg-slate-900/40 p-4">
        <h3 className="text-sm font-semibold text-slate-100">{t('arbitrage.watchlist.addTitle')}</h3>
        <p className="text-xs text-slate-400">{t('arbitrage.watchlist.addSubtitle')}</p>
        <div className="flex flex-wrap items-end gap-2 text-xs">
          <label className="flex flex-col gap-1">
            <span className="text-slate-400">{t('arbitrage.watchlist.minMargin')}</span>
            <input
              type="number"
              step="0.001"
              min="0"
              value={minMargin}
              onChange={(e) => setMinMargin(e.target.value)}
              className="w-28 rounded-md border border-slate-700 bg-slate-900/70 px-2 py-1.5 tabular-nums text-slate-100 outline-none focus:border-cyan-400/60"
            />
          </label>
          <div className="flex flex-wrap gap-1">
            {ALL_MARKETS.map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => toggleMarket(m)}
                className={cn(
                  'rounded-full px-3 py-1.5 text-xs font-semibold transition-colors',
                  selectedMarkets.includes(m)
                    ? 'bg-cyan-500/20 text-cyan-200'
                    : 'bg-slate-800/60 text-slate-400 hover:bg-slate-800',
                )}
              >
                {t(`positions.market.${m}`) || m}
              </button>
            ))}
          </div>
          <Button type="submit" disabled={submitting} className="!h-9 !px-4">
            {submitting ? t('common.saving') : t('arbitrage.watchlist.addSubmit')}
          </Button>
        </div>
        {error ? <p className="text-xs text-rose-400">{error}</p> : null}
      </form>

      <div className="space-y-2">
        {rules === null ? (
          <div className="h-12 animate-pulse rounded-xl bg-slate-800/60" />
        ) : rules.length === 0 ? (
          <p className="text-xs text-slate-500">{t('arbitrage.watchlist.empty')}</p>
        ) : (
          rules.map((rule) => (
            <div
              key={rule.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-800/70 bg-slate-900/40 px-3 py-2 text-xs"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-semibold text-slate-100">
                  ≥ {(rule.minProfitMargin * 100).toFixed(2)}%
                </span>
                <span className="text-slate-400">
                  {rule.marketTypes && rule.marketTypes.length > 0
                    ? rule.marketTypes.join(' · ')
                    : t('arbitrage.watchlist.anyMarket')}
                </span>
                {!rule.notifyEnabled ? (
                  <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] uppercase text-slate-500">
                    {t('arbitrage.watchlist.muted')}
                  </span>
                ) : null}
              </div>
              <button
                type="button"
                onClick={() => remove(rule.id)}
                className="rounded-md p-1 text-slate-400 hover:bg-rose-500/20 hover:text-rose-200"
                aria-label={t('arbitrage.watchlist.delete')}
              >
                <Trash2 size={14} />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
