import { Card, CardBody } from '@/components/ui/Card';
import { ValueSignalBadge } from '@/components/prediction/ValueSignalBadge';
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
  return (
    <Card>
      <CardBody>
        <div className="flex items-center justify-between">
          <div className="text-xs uppercase tracking-wider text-slate-500">最高价值信号</div>
          <ValueSignalBadge level={signalLevel} hideEmpty />
        </div>
        <div className="mt-3 text-2xl font-bold text-slate-900">{outcome}</div>
        <div className="mt-1 text-sm text-slate-500">
          {bookmaker} · 赔率 <span className="font-semibold text-slate-700">{bestOdds.toFixed(2)}</span>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-4">
          <Stat label="EV" value={formatSignedPercent(ev)} good={ev >= 0} />
          <Stat label="Edge" value={formatSignedPercent(edge)} good={edge >= 0} />
        </div>
      </CardBody>
    </Card>
  );
}

function Stat({ label, value, good }: { label: string; value: string; good: boolean }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wider text-slate-500">{label}</div>
      <div
        className={`text-xl font-bold tabular-nums ${good ? 'text-emerald-600' : 'text-rose-600'}`}
      >
        {value}
      </div>
    </div>
  );
}
