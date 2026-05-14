'use client';

import { useState } from 'react';

import { useT } from '@/i18n/I18nProvider';
import { readOpportunityField } from '@/lib/arbitrageApi';
import { cn } from '@/lib/utils';
import type { ArbOpportunity } from '@/types/arbitrage';

interface Props {
  opportunity: ArbOpportunity;
  /** Bankroll input drives the per-leg stake calculator. */
  defaultBankroll?: number;
}

function toNumber(v: number | string | null | undefined): number {
  if (typeof v === 'number') return v;
  if (typeof v === 'string') {
    const n = Number.parseFloat(v);
    return Number.isFinite(n) ? n : 0;
  }
  return 0;
}

export function ArbOpportunityCard({ opportunity, defaultBankroll = 1000 }: Props) {
  const t = useT();
  const [bankroll, setBankroll] = useState(defaultBankroll);

  const margin = toNumber(
    readOpportunityField<number | string>(opportunity, 'profit_margin', 'profitMargin'),
  );
  const market = (readOpportunityField<string>(opportunity, 'market_type', 'marketType') ?? '1x2') as string;
  const matchId = readOpportunityField<number>(opportunity, 'match_id', 'matchId');
  const bestOdds =
    readOpportunityField<Record<string, { odds: number | string; bookmaker: string }>>(
      opportunity, 'best_odds', 'bestOdds',
    ) ?? {};
  const stakeDist =
    readOpportunityField<Record<string, number | string>>(
      opportunity, 'stake_distribution', 'stakeDistribution',
    ) ?? {};
  const detectedAt =
    readOpportunityField<string>(opportunity, 'detected_at', 'detectedAt') ?? '';

  const guaranteedProfit = (margin * bankroll).toFixed(2);

  const highlightClass =
    margin >= 0.02
      ? 'border-emerald-500/40 bg-emerald-500/10'
      : margin >= 0.01
        ? 'border-cyan-500/40 bg-cyan-500/5'
        : 'border-slate-800/70 bg-slate-900/40';

  return (
    <div className={cn('rounded-xl border px-4 py-3', highlightClass)}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-slate-100">
            {t(`positions.market.${market}`) || market.toUpperCase()}
          </span>
          {matchId != null ? (
            <span className="text-xs text-slate-400">
              {t('positions.matchRef').replace('{id}', String(matchId))}
            </span>
          ) : null}
        </div>
        <span className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-sm font-bold text-emerald-300">
          +{(margin * 100).toFixed(2)}%
        </span>
      </div>

      <div className="mt-2 grid gap-2 sm:grid-cols-3">
        {Object.entries(bestOdds).map(([outcome, quote]) => {
          const frac = toNumber(stakeDist[outcome]);
          return (
            <div key={outcome} className="rounded-lg border border-slate-800 bg-slate-950/40 px-2 py-2 text-xs">
              <div className="text-[10px] uppercase tracking-wide text-slate-500">
                {t(`positions.outcome.${outcome}`) || outcome}
              </div>
              <div className="font-mono text-base text-slate-100">{toNumber(quote.odds).toFixed(3)}</div>
              <div className="text-slate-400">{quote.bookmaker}</div>
              <div className="mt-1 text-emerald-300">
                {t('arbitrage.stakeShare')}: {(frac * 100).toFixed(1)}%
                <span className="ml-2 text-slate-300">
                  ≈ ¥{(bankroll * frac).toFixed(2)}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs">
        <label className="flex items-center gap-2 text-slate-400">
          <span>{t('arbitrage.bankroll')}:</span>
          <input
            type="number"
            min="1"
            value={bankroll}
            onChange={(e) => setBankroll(Math.max(1, Number.parseFloat(e.target.value) || 0))}
            className="w-28 rounded-md border border-slate-700 bg-slate-900/70 px-2 py-1 tabular-nums text-slate-100 outline-none focus:border-cyan-400/60"
          />
        </label>
        <div className="text-slate-300">
          {t('arbitrage.guaranteedProfit')}:{' '}
          <span className="font-semibold tabular-nums text-emerald-300">¥{guaranteedProfit}</span>
        </div>
      </div>
      {detectedAt ? (
        <p className="mt-1 text-[10px] text-slate-500">
          {t('arbitrage.detectedAt')}: {new Date(detectedAt).toLocaleString()}
        </p>
      ) : null}
    </div>
  );
}
