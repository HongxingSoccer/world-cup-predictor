'use client';

import { Card, CardBody } from '@/components/ui/Card';
import { ValueSignalBadge } from '@/components/prediction/ValueSignalBadge';
import { useT } from '@/i18n/I18nProvider';
import { formatSignedPercent } from '@/lib/utils';
import type { SignalLevel } from '@/types';

interface ValueSignalCardProps {
  outcome: string;
  ev: number;
  edge: number;
  bookmaker: string;
  bestOdds: number;
  signalLevel: SignalLevel;
}

export function ValueSignalCard({
  outcome,
  ev,
  edge,
  bookmaker,
  bestOdds,
  signalLevel,
}: ValueSignalCardProps) {
  const t = useT();
  return (
    <Card>
      <CardBody>
        <div className="flex items-center justify-between">
          <div className="text-xs uppercase tracking-wider text-slate-400">
            {t('match.topValueSignal')}
          </div>
          <ValueSignalBadge level={signalLevel} hideEmpty />
        </div>
        <div className="mt-3 text-2xl font-bold text-slate-100">{outcome}</div>
        <div className="mt-1 text-sm text-slate-400">
          {bookmaker} · {t('match.oddsLabel')}{' '}
          <span className="font-semibold text-slate-300">{bestOdds.toFixed(2)}</span>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-4">
          <Stat label={t('match.evShort')} value={formatSignedPercent(ev)} good={ev >= 0} />
          <Stat label={t('match.edgeShort')} value={formatSignedPercent(edge)} good={edge >= 0} />
        </div>
      </CardBody>
    </Card>
  );
}

function Stat({ label, value, good }: { label: string; value: string; good: boolean }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wider text-slate-400">{label}</div>
      <div
        className={`text-xl font-bold tabular-nums ${good ? 'text-emerald-300' : 'text-rose-400'}`}
      >
        {value}
      </div>
    </div>
  );
}
