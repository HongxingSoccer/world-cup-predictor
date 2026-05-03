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
    },
    {
      label: 'ROI',
      value: overview ? formatSignedPercent(overview.roi) : '—',
      detail: overview ? `单位投注` : '加载中…',
      good: (overview?.roi ?? 0) >= 0,
    },
    {
      label: '当前连续',
      value: overview ? `${overview.currentStreak >= 0 ? '+' : ''}${overview.currentStreak}` : '—',
      detail: overview && overview.currentStreak > 0 ? '🔥 连红' : overview && overview.currentStreak < 0 ? '连黑' : '',
      good: (overview?.currentStreak ?? 0) >= 0,
    },
    {
      label: '历史最佳',
      value: overview ? `${overview.bestStreak}` : '—',
      detail: overview ? '场连红' : '加载中…',
    },
  ] as const;

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {stats.map((s) => (
        <Card key={s.label}>
          <CardBody>
            <div className="text-xs uppercase tracking-wider text-slate-500">{s.label}</div>
            <div
              className={`mt-1 text-2xl font-black tabular-nums ${
                'good' in s
                  ? s.good
                    ? 'text-emerald-600'
                    : 'text-rose-600'
                  : 'text-slate-900'
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
