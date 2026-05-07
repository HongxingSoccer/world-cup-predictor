import { Card, CardBody } from '@/components/ui/Card';
import { formatPercent, formatSignedPercent } from '@/lib/utils';
import type { TrackRecordOverview } from '@/types';

interface StatsOverviewProps {
  overview: TrackRecordOverview | undefined;
}

export function StatsOverview({ overview }: StatsOverviewProps) {
  const stats = [
    {
      label: '总命中率',
      value: overview ? formatPercent(overview.hitRate) : '—',
      detail: overview ? `${overview.hits} / ${overview.totalPredictions}` : '加载中…',
      hero: true,
    },
    {
      label: 'ROI',
      value: overview ? formatSignedPercent(overview.roi) : '—',
      detail: '单位投注',
      good: (overview?.roi ?? 0) >= 0,
    },
    {
      label: '当前连续',
      value: overview
        ? `${overview.currentStreak >= 0 ? '+' : ''}${overview.currentStreak}`
        : '—',
      detail:
        overview && overview.currentStreak > 0
          ? '🔥 连红'
          : overview && overview.currentStreak < 0
            ? '连黑'
            : '—',
      good: (overview?.currentStreak ?? 0) >= 0,
    },
    {
      label: '历史最佳',
      value: overview ? `${overview.bestStreak}` : '—',
      detail: '场连红',
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
