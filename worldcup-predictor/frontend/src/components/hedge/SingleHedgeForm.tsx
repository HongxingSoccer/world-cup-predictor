'use client';

import { useMemo, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Card, CardBody } from '@/components/ui/Card';
import { useT } from '@/i18n/I18nProvider';
import type {
  CreateScenarioRequest,
  HedgeMode,
  MarketType,
  OutcomeType,
} from '@/types/hedge';
import { MODE_DEFAULT_RATIO, modeFromRatio } from '@/types/hedge';

import { HedgeModeSlider } from './HedgeModeSlider';

interface Props {
  onSubmit: (req: CreateScenarioRequest) => void | Promise<void>;
  isSubmitting: boolean;
}

const OUTCOMES_BY_MARKET: Record<MarketType, OutcomeType[]> = {
  '1x2': ['home', 'draw', 'away'],
  over_under: ['over', 'under'],
  asian_handicap: ['home', 'away'],
  // GAP 7: btts disabled in this PR. Type-only entry to keep the
  // Record exhaustive; the UI never renders this market as selectable.
  btts: [],
};

export function SingleHedgeForm({ onSubmit, isSubmitting }: Props) {
  const t = useT();

  const [matchId, setMatchId] = useState<string>('');
  const [stake, setStake] = useState<string>('100');
  const [odds, setOdds] = useState<string>('2.10');
  const [market, setMarket] = useState<MarketType>('1x2');
  const [outcome, setOutcome] = useState<OutcomeType>('home');
  const [mode, setMode] = useState<HedgeMode>('full');
  /** Slider 0–100, kept in sync with mode. */
  const [ratioPct, setRatioPct] = useState<number>(100);

  const error = useMemo(() => {
    const m = Number(matchId);
    if (!Number.isInteger(m) || m <= 0) {
      return t('hedge.validation.matchIdRequired');
    }
    const s = Number(stake);
    if (!(s > 0)) return t('hedge.validation.stakeGreaterThanZero');
    const o = Number(odds);
    if (!(o > 1.0)) return t('hedge.validation.oddsGreaterThanOne');
    return null;
  }, [matchId, stake, odds, t]);

  const handleModeChange = (next: HedgeMode) => {
    setMode(next);
    // Snap slider to the canonical ratio for the chosen mode.
    setRatioPct(MODE_DEFAULT_RATIO[next] * 100);
  };

  const handleRatioChange = (next: number) => {
    setRatioPct(next);
    const inferred = modeFromRatio(next / 100);
    if (inferred !== mode) setMode(inferred);
  };

  const handleMarketChange = (next: MarketType) => {
    setMarket(next);
    // Reset outcome to a valid value for the new market.
    const allowed = OUTCOMES_BY_MARKET[next];
    if (allowed.length > 0 && !allowed.includes(outcome)) {
      setOutcome(allowed[0]);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (error) return;
    onSubmit({
      scenarioType: 'single',
      matchId: Number(matchId),
      originalStake: Number(stake),
      originalOdds: Number(odds),
      originalOutcome: outcome,
      originalMarket: market,
      hedgeMode: mode,
      hedgeRatio: ratioPct / 100,
    });
  };

  return (
    <Card>
      <CardBody>
        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="grid gap-4 md:grid-cols-2">
            <Field label={t('hedge.singleForm.matchId')}>
              <input
                type="number"
                inputMode="numeric"
                min={1}
                value={matchId}
                onChange={(e) => setMatchId(e.target.value)}
                placeholder="12345"
                className="wcp-input"
              />
              <p className="mt-1 text-xs text-slate-500">
                {t('hedge.singleForm.matchIdHint')}
              </p>
            </Field>

            <Field label={t('hedge.singleForm.originalStake')}>
              <input
                type="number"
                inputMode="decimal"
                step="0.01"
                min={0}
                value={stake}
                onChange={(e) => setStake(e.target.value)}
                className="wcp-input"
              />
            </Field>

            <Field label={t('hedge.singleForm.originalOdds')}>
              <input
                type="number"
                inputMode="decimal"
                step="0.01"
                min={1.01}
                value={odds}
                onChange={(e) => setOdds(e.target.value)}
                className="wcp-input"
              />
            </Field>

            <Field label={t('hedge.singleForm.originalMarket')}>
              <select
                value={market}
                onChange={(e) => handleMarketChange(e.target.value as MarketType)}
                className="wcp-input"
              >
                <option value="1x2">{t('hedge.markets.1x2')}</option>
                <option value="over_under">{t('hedge.markets.over_under')}</option>
                <option value="asian_handicap">
                  {t('hedge.markets.asian_handicap')}
                </option>
                <option value="btts" disabled>
                  {t('hedge.markets.btts_disabled')}
                </option>
              </select>
            </Field>

            <Field label={t('hedge.singleForm.originalOutcome')}>
              <select
                value={outcome}
                onChange={(e) => setOutcome(e.target.value as OutcomeType)}
                className="wcp-input"
              >
                {OUTCOMES_BY_MARKET[market].map((o) => (
                  <option key={o} value={o}>
                    {t(`hedge.outcomes.${o}`)}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          <fieldset className="space-y-3">
            <legend className="mb-2 text-sm font-medium text-slate-200">
              {t('hedge.singleForm.hedgeMode')}
            </legend>
            <div className="grid gap-2 md:grid-cols-3">
              {(['full', 'partial', 'risk'] as HedgeMode[]).map((m) => (
                <label
                  key={m}
                  className={`flex cursor-pointer flex-col rounded-lg border px-3 py-2 transition-colors ${
                    mode === m
                      ? 'border-brand-500/60 bg-brand-500/10'
                      : 'border-slate-700 bg-slate-900/40 hover:border-slate-600'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="hedge-mode"
                      value={m}
                      checked={mode === m}
                      onChange={() => handleModeChange(m)}
                      className="accent-brand-500"
                    />
                    <span className="font-semibold text-slate-100">
                      {t(`hedge.modes.${m}`)}
                    </span>
                  </div>
                  <span className="mt-1 text-xs text-slate-400">
                    {t(`hedge.modes.${m}Desc`)}
                  </span>
                </label>
              ))}
            </div>

            <HedgeModeSlider value={ratioPct} onChange={handleRatioChange} />
          </fieldset>

          {error && (
            <p className="text-sm text-rose-400" role="alert">
              {error}
            </p>
          )}

          <Button
            type="submit"
            variant="primary"
            size="lg"
            disabled={!!error}
            loading={isSubmitting}
            className="w-full md:w-auto"
          >
            {t('hedge.submit')}
          </Button>
        </form>
      </CardBody>
    </Card>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-slate-200">{label}</span>
      {children}
    </label>
  );
}
