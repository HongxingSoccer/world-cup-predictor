'use client';

import { Card, CardBody } from '@/components/ui/Card';
import { useT } from '@/i18n/I18nProvider';
import { formatPercent, formatSignedPercent } from '@/lib/utils';
import type { TrackRecordOverview } from '@/types';

interface StatsOverviewProps {
  overview: TrackRecordOverview | undefined;
}

export function StatsOverview({ overview }: StatsOverviewProps) {
  const t = useT();
  const stats = [
    {
      label: t('trackRecord.hitRate'),
      value: overview ? formatPercent(overview.hitRate) : '—',
      detail: overview ? `${overview.hits} / ${overview.totalPredictions}` : t('common.loading'),
      hero: true,
    },
    {
      label: t('trackRecord.roi'),
      value: overview ? formatSignedPercent(overview.roi) : '—',
      detail: t('trackRecord.unitBet'),
      good: (overview?.roi ?? 0) >= 0,
    },
    {
      label: t('trackRecord.currentStreak'),
      value: overview
        ? `${overview.currentStreak >= 0 ? '+' : ''}${overview.currentStreak}`
        : '—',
      detail:
        overview && overview.currentStreak > 0
          ? t('trackRecord.hotStreak')
          : overview && overview.currentStreak < 0
            ? t('trackRecord.coldStreak')
            : '—',
      good: (overview?.currentStreak ?? 0) >= 0,
    },
    {
      label: t('trackRecord.bestEver'),
      value: overview ? `${overview.bestStreak}` : '—',
      detail: t('trackRecord.streakUnit'),
      hero: true,
    },
  ] as const;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {stats.map((s) => (
        <Card key={s.label}>
          <CardBody>
            <div className="text-xs uppercase tracking-wider text-slate-400">{s.label}</div>
            <div
              className={`mt-1 text-2xl font-black tabular-nums ${
                'hero' in s && s.hero
                  ? 'hero-number'
                  : 'good' in s
                    ? s.good
                      ? 'text-emerald-300'
                      : 'text-rose-400'
                    : 'text-slate-100'
              }`}
            >
              {s.value}
            </div>
            <div className="mt-1 text-xs text-slate-500">{s.detail}</div>
          </CardBody>
        </Card>
      ))}
    </div>
  );
}
