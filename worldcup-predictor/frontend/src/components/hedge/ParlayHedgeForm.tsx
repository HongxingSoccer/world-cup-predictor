'use client';

import { Plus, Trash2 } from 'lucide-react';
import { useMemo, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Card, CardBody } from '@/components/ui/Card';
import { useT } from '@/i18n/I18nProvider';
import type {
  CreateScenarioRequest,
  HedgeMode,
  ParlayLegInput,
} from '@/types/hedge';
import { MODE_DEFAULT_RATIO, modeFromRatio } from '@/types/hedge';

import { HedgeModeSlider } from './HedgeModeSlider';

interface Props {
  onSubmit: (req: CreateScenarioRequest) => void | Promise<void>;
  isSubmitting: boolean;
}

const MAX_LEGS = 8;
const MIN_LEGS = 2;

type DraftLeg = {
  matchId: string; // string for controlled input; coerced on submit
  outcome: string;
  odds: string;
  isSettled: boolean;
  isWon: boolean;
};

function emptyLeg(): DraftLeg {
  return { matchId: '', outcome: 'home', odds: '2.00', isSettled: false, isWon: false };
}

export function ParlayHedgeForm({ onSubmit, isSubmitting }: Props) {
  const t = useT();

  const [stake, setStake] = useState<string>('50');
  const [legs, setLegs] = useState<DraftLeg[]>([
    { matchId: '', outcome: 'home', odds: '1.85', isSettled: true, isWon: true },
    { matchId: '', outcome: 'over', odds: '1.90', isSettled: true, isWon: true },
    { matchId: '', outcome: 'home', odds: '2.20', isSettled: false, isWon: false },
  ]);
  const [mode, setMode] = useState<HedgeMode>('full');
  const [ratioPct, setRatioPct] = useState<number>(100);

  const error = useMemo(() => {
    if (!(Number(stake) > 0)) return t('hedge.validation.stakeGreaterThanZero');
    if (legs.length < MIN_LEGS) return t('hedge.validation.legsAtLeastTwo');
    const unsettled = legs.filter((l) => !l.isSettled).length;
    if (unsettled !== 1) return t('hedge.validation.legsExactlyOneUnsettled');
    for (const l of legs) {
      if (!Number.isInteger(Number(l.matchId)) || Number(l.matchId) <= 0) {
        return t('hedge.validation.matchIdRequired');
      }
      if (!(Number(l.odds) > 1.0)) return t('hedge.validation.oddsGreaterThanOne');
      if (l.isSettled && !l.isWon) return t('hedge.validation.settledLegMustBeWon');
    }
    return null;
  }, [stake, legs, t]);

  const handleModeChange = (next: HedgeMode) => {
    setMode(next);
    setRatioPct(MODE_DEFAULT_RATIO[next] * 100);
  };
  const handleRatioChange = (next: number) => {
    setRatioPct(next);
    const inferred = modeFromRatio(next / 100);
    if (inferred !== mode) setMode(inferred);
  };

  const updateLeg = (i: number, patch: Partial<DraftLeg>) => {
    setLegs((prev) => prev.map((leg, idx) => (idx === i ? { ...leg, ...patch } : leg)));
  };
  const addLeg = () => {
    if (legs.length >= MAX_LEGS) return;
    setLegs((prev) => [...prev, emptyLeg()]);
  };
  const removeLeg = (i: number) => {
    if (legs.length <= MIN_LEGS) return;
    setLegs((prev) => prev.filter((_, idx) => idx !== i));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (error) return;
    const serialised: ParlayLegInput[] = legs.map((l) => ({
      matchId: Number(l.matchId),
      outcome: l.outcome,
      odds: Number(l.odds),
      isSettled: l.isSettled,
      // Only send isWon when the leg is settled — for unsettled legs the
      // value is meaningless and the backend stores it as null.
      isWon: l.isSettled ? l.isWon : null,
    }));
    onSubmit({
      scenarioType: 'parlay',
      originalStake: Number(stake),
      hedgeMode: mode,
      hedgeRatio: ratioPct / 100,
      legs: serialised,
    });
  };

  return (
    <Card>
      <CardBody>
        <form onSubmit={handleSubmit} className="space-y-5">
          <label className="block max-w-xs">
            <span className="mb-1 block text-sm font-medium text-slate-200">
              {t('hedge.parlayForm.stake')}
            </span>
            <input
              type="number"
              inputMode="decimal"
              step="0.01"
              min={0}
              value={stake}
              onChange={(e) => setStake(e.target.value)}
              className="wcp-input"
            />
          </label>

          <fieldset className="space-y-3">
            <legend className="mb-1 text-sm font-medium text-slate-200">
              {t('hedge.parlayForm.legs')}
            </legend>
            <div className="space-y-2">
              {legs.map((leg, i) => (
                <div
                  key={i}
                  className="rounded-lg border border-slate-700 bg-slate-900/40 p-3"
                >
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                      {t('hedge.parlayForm.legHeading').replace('{n}', String(i + 1))}
                    </span>
                    {legs.length > MIN_LEGS && (
                      <button
                        type="button"
                        onClick={() => removeLeg(i)}
                        className="text-rose-400 transition-colors hover:text-rose-300"
                        aria-label={t('hedge.parlayForm.removeLeg')}
                      >
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>
                  <div className="grid gap-2 md:grid-cols-4">
                    <LegField label={t('hedge.parlayForm.legMatchId')}>
                      <input
                        type="number"
                        inputMode="numeric"
                        min={1}
                        value={leg.matchId}
                        onChange={(e) => updateLeg(i, { matchId: e.target.value })}
                        className="wcp-input"
                      />
                    </LegField>
                    <LegField label={t('hedge.parlayForm.legOutcome')}>
                      <input
                        type="text"
                        value={leg.outcome}
                        onChange={(e) => updateLeg(i, { outcome: e.target.value })}
                        className="wcp-input"
                      />
                    </LegField>
                    <LegField label={t('hedge.parlayForm.legOdds')}>
                      <input
                        type="number"
                        inputMode="decimal"
                        step="0.01"
                        min={1.01}
                        value={leg.odds}
                        onChange={(e) => updateLeg(i, { odds: e.target.value })}
                        className="wcp-input"
                      />
                    </LegField>
                    <div className="flex items-end gap-3">
                      <label className="flex items-center gap-1.5 text-xs text-slate-300">
                        <input
                          type="checkbox"
                          checked={leg.isSettled}
                          onChange={(e) =>
                            updateLeg(i, {
                              isSettled: e.target.checked,
                              // toggling off settled also resets isWon
                              isWon: e.target.checked ? leg.isWon : false,
                            })
                          }
                          className="accent-brand-500"
                        />
                        {t('hedge.parlayForm.legIsSettled')}
                      </label>
                      <label
                        className={`flex items-center gap-1.5 text-xs ${
                          leg.isSettled ? 'text-slate-300' : 'text-slate-600'
                        }`}
                      >
                        <input
                          type="checkbox"
                          disabled={!leg.isSettled}
                          checked={leg.isWon}
                          onChange={(e) => updateLeg(i, { isWon: e.target.checked })}
                          className="accent-brand-500"
                        />
                        {t('hedge.parlayForm.legWon')}
                      </label>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <div className="flex items-center gap-3 text-xs text-slate-500">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={addLeg}
                disabled={legs.length >= MAX_LEGS}
                leftIcon={<Plus size={14} />}
              >
                {t('hedge.parlayForm.addLeg')}
              </Button>
              <span>
                {legs.length >= MAX_LEGS
                  ? t('hedge.parlayForm.maxLegsHint')
                  : t('hedge.parlayForm.minLegsHint')}
              </span>
            </div>
          </fieldset>

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
                      name="parlay-hedge-mode"
                      value={m}
                      checked={mode === m}
                      onChange={() => handleModeChange(m)}
                      className="accent-brand-500"
                    />
                    <span className="font-semibold text-slate-100">
                      {t(`hedge.modes.${m}`)}
                    </span>
                  </div>
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

function LegField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-slate-500">{label}</span>
      {children}
    </label>
  );
}
