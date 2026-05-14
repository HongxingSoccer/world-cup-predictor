'use client';

import { useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { useT } from '@/i18n/I18nProvider';
import { createPosition } from '@/lib/positionsApi';
import type { PositionMarket, PositionResponse } from '@/types/positions';

const MARKETS: PositionMarket[] = ['1x2', 'over_under', 'asian_handicap', 'btts'];

const OUTCOMES_BY_MARKET: Record<PositionMarket, string[]> = {
  '1x2': ['home', 'draw', 'away'],
  over_under: ['over', 'under'],
  asian_handicap: ['home', 'away'],
  btts: ['yes', 'no'],
};

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: (position: PositionResponse) => void;
  /** Optional pre-fill (e.g. from a match-detail page). */
  initialMatchId?: number | null;
}

export function CreatePositionForm({ open, onClose, onCreated, initialMatchId }: Props) {
  const t = useT();
  const [matchId, setMatchId] = useState<string>(
    initialMatchId != null ? String(initialMatchId) : '',
  );
  const [platform, setPlatform] = useState('');
  const [market, setMarket] = useState<PositionMarket>('1x2');
  const [outcome, setOutcome] = useState('home');
  const [stake, setStake] = useState('');
  const [odds, setOdds] = useState('');
  const [placedAt, setPlacedAt] = useState('');
  const [notes, setNotes] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reset = () => {
    setMatchId('');
    setPlatform('');
    setMarket('1x2');
    setOutcome('home');
    setStake('');
    setOdds('');
    setPlacedAt('');
    setNotes('');
    setError(null);
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);

    const matchIdNum = Number.parseInt(matchId, 10);
    const stakeNum = Number.parseFloat(stake);
    const oddsNum = Number.parseFloat(odds);
    if (!Number.isFinite(matchIdNum) || matchIdNum <= 0) {
      setError(t('positions.errorMatchId'));
      return;
    }
    if (!Number.isFinite(stakeNum) || stakeNum <= 0) {
      setError(t('positions.errorStake'));
      return;
    }
    if (!Number.isFinite(oddsNum) || oddsNum <= 1) {
      setError(t('positions.errorOdds'));
      return;
    }

    setPending(true);
    try {
      const created = await createPosition({
        matchId: matchIdNum,
        platform: platform.trim() || null,
        market,
        outcome,
        stake: stakeNum,
        odds: oddsNum,
        placedAt: placedAt ? new Date(placedAt).toISOString() : null,
        notes: notes.trim() || null,
      });
      reset();
      onCreated(created);
      onClose();
    } catch (err) {
      const message = err instanceof Error ? err.message : t('positions.errorGeneric');
      setError(message);
    } finally {
      setPending(false);
    }
  };

  const onMarketChange = (next: PositionMarket) => {
    setMarket(next);
    setOutcome(OUTCOMES_BY_MARKET[next][0]);
  };

  return (
    <Modal open={open} onClose={onClose} title={t('positions.formTitle')}>
      <form onSubmit={submit} className="space-y-3 text-sm">
        <Field label={t('positions.fieldMatchId')}>
          <input
            type="number"
            value={matchId}
            onChange={(e) => setMatchId(e.target.value)}
            className={INPUT_CLASS}
            required
          />
        </Field>

        <Field label={t('positions.fieldPlatform')}>
          <input
            value={platform}
            onChange={(e) => setPlatform(e.target.value)}
            placeholder="Pinnacle / Bet365 / …"
            className={INPUT_CLASS}
          />
        </Field>

        <div className="grid grid-cols-2 gap-3">
          <Field label={t('positions.fieldMarket')}>
            <select
              value={market}
              onChange={(e) => onMarketChange(e.target.value as PositionMarket)}
              className={INPUT_CLASS}
            >
              {MARKETS.map((m) => (
                <option key={m} value={m}>
                  {t(`positions.market.${m}`)}
                </option>
              ))}
            </select>
          </Field>
          <Field label={t('positions.fieldOutcome')}>
            <select
              value={outcome}
              onChange={(e) => setOutcome(e.target.value)}
              className={INPUT_CLASS}
            >
              {OUTCOMES_BY_MARKET[market].map((o) => (
                <option key={o} value={o}>
                  {t(`positions.outcome.${o}`)}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Field label={t('positions.fieldStake')}>
            <input
              type="number"
              step="0.01"
              min="0.01"
              value={stake}
              onChange={(e) => setStake(e.target.value)}
              className={INPUT_CLASS}
              required
            />
          </Field>
          <Field label={t('positions.fieldOdds')}>
            <input
              type="number"
              step="0.01"
              min="1.01"
              value={odds}
              onChange={(e) => setOdds(e.target.value)}
              className={INPUT_CLASS}
              required
            />
          </Field>
        </div>

        <Field label={t('positions.fieldPlacedAt')}>
          <input
            type="datetime-local"
            value={placedAt}
            onChange={(e) => setPlacedAt(e.target.value)}
            className={INPUT_CLASS}
          />
        </Field>

        <Field label={t('positions.fieldNotes')}>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
            className={INPUT_CLASS}
          />
        </Field>

        {error ? <p className="text-xs text-rose-400">{error}</p> : null}

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="ghost" onClick={onClose} disabled={pending}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={pending}>
            {pending ? t('common.saving') : t('positions.formSubmit')}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

const INPUT_CLASS =
  'w-full rounded-md border border-slate-700 bg-slate-900/70 px-2 py-1.5 text-sm text-slate-100 outline-none focus:border-cyan-400/60';

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs text-slate-400">{label}</span>
      {children}
    </label>
  );
}
