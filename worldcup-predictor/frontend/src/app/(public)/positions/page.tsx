'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useMemo, useState } from 'react';

import { CreatePositionForm } from '@/components/positions/CreatePositionForm';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { useAuth } from '@/hooks/useAuth';
import { useSubscription } from '@/hooks/useSubscription';
import { useT } from '@/i18n/I18nProvider';
import { cn } from '@/lib/utils';
import {
  deletePosition,
  listPositions,
  updatePositionStatus,
} from '@/lib/positionsApi';
import type { PositionResponse, PositionStatus } from '@/types/positions';

const ACTIVE_ALERT_WINDOW_MIN = 30;
const STATUS_FILTERS: Array<{ value: 'all' | PositionStatus; labelKey: string }> = [
  { value: 'all', labelKey: 'positions.filterAll' },
  { value: 'active', labelKey: 'positions.status.active' },
  { value: 'hedged', labelKey: 'positions.status.hedged' },
  { value: 'settled', labelKey: 'positions.status.settled' },
  { value: 'cancelled', labelKey: 'positions.status.cancelled' },
];

function hasFreshAlert(lastAlertAt: string | null): boolean {
  if (!lastAlertAt) return false;
  const fired = new Date(lastAlertAt).getTime();
  if (Number.isNaN(fired)) return false;
  return Date.now() - fired < ACTIVE_ALERT_WINDOW_MIN * 60_000;
}

export default function PositionsPage() {
  const t = useT();
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const { tier } = useSubscription();
  const [filter, setFilter] = useState<'all' | PositionStatus>('all');
  const [positions, setPositions] = useState<PositionResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  useEffect(() => {
    if (typeof window !== 'undefined' && !isAuthenticated) {
      router.replace('/login?next=/positions');
    }
  }, [isAuthenticated, router]);

  const tierLocked = isAuthenticated && tier === 'free';

  useEffect(() => {
    if (!isAuthenticated || tierLocked) return;
    let cancelled = false;
    setPositions(null);
    setError(null);
    (async () => {
      try {
        const status = filter === 'all' ? undefined : filter;
        const rows = await listPositions(status);
        if (cancelled) return;
        setPositions(rows);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : t('positions.loadFailed'));
        setPositions([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [filter, isAuthenticated, tierLocked, t]);

  const alertCount = useMemo(
    () => (positions ?? []).filter((p) => p.status === 'active' && hasFreshAlert(p.lastAlertAt)).length,
    [positions],
  );

  if (!isAuthenticated) {
    return null;
  }

  if (tierLocked) {
    return (
      <div className="space-y-3">
        <h1 className="text-xl font-bold text-slate-100">{t('positions.title')}</h1>
        <Card>
          <CardBody className="space-y-3 text-sm text-slate-300">
            <p>{t('positions.tierLocked')}</p>
            <Button onClick={() => router.push('/subscribe')}>{t('nav.subscribe')}</Button>
          </CardBody>
        </Card>
      </div>
    );
  }

  const onCreated = (created: PositionResponse) => {
    setPositions((prev) => (prev == null ? [created] : [created, ...prev]));
  };

  const onChangeStatus = async (id: number, next: PositionStatus) => {
    try {
      const updated = await updatePositionStatus(id, { status: next });
      setPositions((prev) => prev?.map((p) => (p.id === id ? updated : p)) ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('positions.updateFailed'));
    }
  };

  const onDelete = async (id: number) => {
    if (typeof window !== 'undefined' && !window.confirm(t('positions.confirmDelete'))) {
      return;
    }
    try {
      const updated = await deletePosition(id);
      setPositions((prev) => prev?.map((p) => (p.id === id ? updated : p)) ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('positions.deleteFailed'));
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h1 className="text-xl font-bold text-slate-100">{t('positions.title')}</h1>
          <p className="mt-1 text-xs text-slate-400">{t('positions.subtitle')}</p>
        </div>
        <div className="flex gap-2">
          {alertCount > 0 ? (
            <span className="inline-flex items-center rounded-full bg-amber-500/15 px-3 py-1 text-xs font-semibold text-amber-300">
              {t('positions.alertBadge').replace('{count}', String(alertCount))}
            </span>
          ) : null}
          <Button onClick={() => setShowForm(true)}>+ {t('positions.create')}</Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center gap-2">
            {STATUS_FILTERS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setFilter(opt.value)}
                className={cn(
                  'rounded-full px-3 py-1 text-xs font-semibold transition-colors',
                  filter === opt.value
                    ? 'bg-cyan-500/20 text-cyan-200'
                    : 'bg-slate-800/60 text-slate-400 hover:bg-slate-800',
                )}
              >
                {t(opt.labelKey)}
              </button>
            ))}
          </div>
        </CardHeader>
        <CardBody className="space-y-2">
          {error ? <p className="text-xs text-rose-400">{error}</p> : null}
          {positions === null ? (
            <div className="space-y-2">
              <div className="h-14 animate-pulse rounded-xl bg-slate-800/60" />
              <div className="h-14 animate-pulse rounded-xl bg-slate-800/60" />
            </div>
          ) : positions.length === 0 ? (
            <p className="py-8 text-center text-sm text-slate-400">{t('positions.empty')}</p>
          ) : (
            positions.map((p) => (
              <PositionRow
                key={p.id}
                position={p}
                onChangeStatus={onChangeStatus}
                onDelete={onDelete}
              />
            ))
          )}
        </CardBody>
      </Card>

      <CreatePositionForm open={showForm} onClose={() => setShowForm(false)} onCreated={onCreated} />
    </div>
  );
}

function PositionRow({
  position,
  onChangeStatus,
  onDelete,
}: {
  position: PositionResponse;
  onChangeStatus: (id: number, status: PositionStatus) => void;
  onDelete: (id: number) => void;
}) {
  const t = useT();
  const alert = position.status === 'active' && hasFreshAlert(position.lastAlertAt);
  const settled = position.status === 'settled';

  return (
    <div
      className={cn(
        'rounded-xl border px-4 py-3 transition-colors',
        alert
          ? 'border-amber-500/40 bg-amber-500/10'
          : 'border-slate-800/70 bg-slate-900/40',
      )}
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="font-semibold text-slate-100">
          {t(`positions.market.${position.market}`)} · {t(`positions.outcome.${position.outcome}`) || position.outcome}
        </span>
        <span className="text-xs text-slate-400">
          {t('positions.matchRef').replace('{id}', String(position.matchId))}
        </span>
        <StatusBadge status={position.status} />
        {alert ? (
          <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-[10px] font-semibold uppercase text-amber-200">
            {t('positions.hedgeWindowOpen')}
          </span>
        ) : null}
      </div>
      <div className="mt-1 grid grid-cols-2 gap-x-4 gap-y-0.5 text-xs text-slate-400 sm:grid-cols-4">
        <div>
          <span className="text-slate-500">{t('positions.fieldStake')}:</span>{' '}
          <span className="tabular-nums text-slate-100">{position.stake}</span>
        </div>
        <div>
          <span className="text-slate-500">{t('positions.fieldOdds')}:</span>{' '}
          <span className="tabular-nums text-slate-100">{position.odds}</span>
        </div>
        <div>
          <span className="text-slate-500">{t('positions.fieldPlatform')}:</span>{' '}
          <span className="text-slate-200">{position.platform ?? '—'}</span>
        </div>
        {settled ? (
          <div>
            <span className="text-slate-500">{t('positions.pnl')}:</span>{' '}
            <span
              className={cn(
                'tabular-nums font-semibold',
                (position.settlementPnl ?? 0) >= 0 ? 'text-emerald-300' : 'text-rose-300',
              )}
            >
              {position.settlementPnl ?? 0}
            </span>
          </div>
        ) : null}
      </div>
      <div className="mt-2 flex flex-wrap gap-2">
        {position.status === 'active' ? (
          <>
            <Button
              variant="ghost"
              onClick={() => onChangeStatus(position.id, 'hedged')}
              className="!h-7 !px-3 !text-xs"
            >
              {t('positions.actionMarkHedged')}
            </Button>
            <a
              href={`/hedge?from_position=${position.id}`}
              className="inline-flex h-7 items-center rounded-md border border-cyan-500/40 bg-cyan-500/10 px-3 text-xs font-semibold text-cyan-200 hover:bg-cyan-500/20"
            >
              {t('positions.actionHedge')}
            </a>
            <Button
              variant="ghost"
              onClick={() => onDelete(position.id)}
              className="!h-7 !px-3 !text-xs !text-rose-300 hover:!text-rose-200"
            >
              {t('positions.actionCancel')}
            </Button>
          </>
        ) : null}
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: PositionStatus }) {
  const t = useT();
  const map: Record<PositionStatus, string> = {
    active: 'bg-cyan-500/15 text-cyan-300',
    hedged: 'bg-emerald-500/15 text-emerald-300',
    settled: 'bg-slate-700 text-slate-300',
    cancelled: 'bg-slate-800 text-slate-500',
  };
  return (
    <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase', map[status])}>
      {t(`positions.status.${status}`)}
    </span>
  );
}
