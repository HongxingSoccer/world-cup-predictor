'use client';

import { useT } from '@/i18n/I18nProvider';
import { Card, CardBody } from '@/components/ui/Card';
import type { HedgeCalculationDto, ScenarioResponse } from '@/types/hedge';

import { ModelInsightBadge } from './ModelInsightBadge';
import { ProfitLossChart } from './ProfitLossChart';

interface Props {
  scenario: ScenarioResponse;
}

function formatYuan(value: number | null): string {
  if (value == null) return '—';
  const fixed = value.toFixed(2);
  return value < 0 ? `-¥${fixed.slice(1)}` : `¥${fixed}`;
}

function formatOdds(value: number | null): string {
  if (value == null) return '—';
  return value.toFixed(3);
}

function profitColor(v: number | null): string {
  if (v == null || v === 0) return 'text-slate-300';
  return v > 0 ? 'text-emerald-400' : 'text-rose-400';
}

/**
 * Recommendation cards rendered horizontally. For parlay scenarios the
 * single calculation row carries `hedge_outcome = 'parlay_last_leg_loses'`
 * — same shape, different display label is handled at the data layer
 * (we just render whatever the server gave us).
 */
export function HedgeResultPanel({ scenario }: Props) {
  const t = useT();

  if (scenario.calculations.length === 0) {
    return (
      <Card>
        <CardBody>
          <p className="text-slate-200">{t('hedge.result.noData')}</p>
          <p className="mt-1 text-sm text-slate-400">
            {t('hedge.result.noDataHint')}
          </p>
        </CardBody>
      </Card>
    );
  }

  return (
    <section aria-labelledby="hedge-results-heading" className="space-y-4">
      <header className="flex items-baseline justify-between">
        <h2
          id="hedge-results-heading"
          className="text-lg font-semibold text-slate-100"
        >
          {t('hedge.result.panelTitle')}
        </h2>
        <span className="text-xs text-slate-500">
          {t('hedge.result.scenarioId')} #{scenario.scenarioId}
        </span>
      </header>

      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
        {scenario.calculations.map((calc) => (
          <CalculationCard key={calc.id} calc={calc} />
        ))}
      </div>

      <p className="text-xs text-slate-500">{scenario.disclaimer}</p>
    </section>
  );
}

function CalculationCard({ calc }: { calc: HedgeCalculationDto }) {
  const t = useT();
  return (
    <Card>
      <CardBody className="space-y-3">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="text-xs uppercase tracking-wide text-slate-500">
              {t('hedge.result.hedgeOutcome')}
            </p>
            <p className="font-semibold text-slate-100">
              {calc.hedgeOutcome.replace('parlay_last_leg_loses', 'Last leg loses')}
            </p>
            <p className="mt-1 text-xs text-slate-400">
              {t('hedge.result.bestBookmaker')}: {calc.hedgeBookmaker} &middot;{' '}
              @{formatOdds(calc.hedgeOdds)}
            </p>
          </div>
          <ModelInsightBadge assessment={calc.modelAssessment} />
        </div>

        <div className="rounded-lg bg-slate-900/60 px-3 py-2">
          <p className="text-xs uppercase tracking-wide text-slate-500">
            {t('hedge.result.hedgeStake')}
          </p>
          <p className="text-2xl font-semibold tabular-nums text-slate-50">
            {formatYuan(calc.hedgeStake)}
          </p>
        </div>

        <ul className="grid grid-cols-3 gap-2 text-xs">
          <li>
            <p className="text-slate-500">{t('hedge.result.profitOrigWins')}</p>
            <p
              className={`mt-0.5 font-semibold tabular-nums ${profitColor(calc.profitIfOriginalWins)}`}
            >
              {formatYuan(calc.profitIfOriginalWins)}
            </p>
          </li>
          <li>
            <p className="text-slate-500">{t('hedge.result.profitHedgeWins')}</p>
            <p
              className={`mt-0.5 font-semibold tabular-nums ${profitColor(calc.profitIfHedgeWins)}`}
            >
              {formatYuan(calc.profitIfHedgeWins)}
            </p>
          </li>
          <li>
            <p className="text-slate-500">{t('hedge.result.maxLoss')}</p>
            <p
              className={`mt-0.5 font-semibold tabular-nums ${profitColor(calc.maxLoss)}`}
            >
              {formatYuan(calc.maxLoss)}
            </p>
          </li>
        </ul>

        {calc.guaranteedProfit != null && (
          <div className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-1.5 text-xs text-emerald-300">
            <span className="font-semibold">
              {t('hedge.result.guaranteedProfit')}:
            </span>{' '}
            {formatYuan(calc.guaranteedProfit)}
          </div>
        )}

        {(calc.evOfHedge != null || calc.modelProbHedge != null) && (
          <div className="grid grid-cols-2 gap-2 text-xs text-slate-400">
            {calc.evOfHedge != null && (
              <div>
                <span className="text-slate-500">
                  {t('hedge.result.modelEv')}:
                </span>{' '}
                <span className={profitColor(calc.evOfHedge)}>
                  {calc.evOfHedge.toFixed(4)}
                </span>
              </div>
            )}
            {calc.modelProbHedge != null && (
              <div>
                <span className="text-slate-500">
                  {t('hedge.result.modelProbHedge')}:
                </span>{' '}
                {(calc.modelProbHedge * 100).toFixed(1)}%
              </div>
            )}
          </div>
        )}

        <div>
          <p className="mb-1 text-xs text-slate-500">
            {t('hedge.result.chartTitle')}
          </p>
          <ProfitLossChart
            profitIfOriginalWins={calc.profitIfOriginalWins}
            profitIfHedgeWins={calc.profitIfHedgeWins}
            maxLoss={calc.maxLoss}
          />
        </div>
      </CardBody>
    </Card>
  );
}
