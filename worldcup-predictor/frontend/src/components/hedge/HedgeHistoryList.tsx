'use client';

import useSWR from 'swr';

import { Card, CardBody } from '@/components/ui/Card';
import { useAuth } from '@/hooks/useAuth';
import { useSubscription } from '@/hooks/useSubscription';
import { useT } from '@/i18n/I18nProvider';
import { fetchHedgeResults, fetchHedgeStats } from '@/lib/hedgeApi';
import { cn } from '@/lib/utils';
import type {
  HedgeHistoryResponse,
  HedgeStatsResponse,
} from '@/types/hedge';

const HEDGE_DISCLAIMER =
  '本平台仅提供数据分析参考,不构成任何投注建议。' +
  '对冲计算器为数学工具,计算结果仅供参考,请用户自行判断。';

function formatYuan(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  const fixed = value.toFixed(2);
  return value < 0 ? `-¥${fixed.slice(1)}` : `¥${fixed}`;
}

function profitColor(v: number | null | undefined): string {
  if (v == null || v === 0) return 'text-slate-300';
  return v > 0 ? 'text-emerald-400' : 'text-rose-400';
}

const DATE_FMT = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
});

/**
 * Skeleton history page.
 *
 * - Top: 5 stat cards from /hedge/stats
 * - Bottom: table of the 10 most-recent settled scenarios from /hedge/results
 *
 * Scenario drill-down (clicking a row) is deferred to a follow-up PR.
 */
export function HedgeHistoryList() {
  const t = useT();
  const { isAuthenticated } = useAuth();
  // `/stats` is basic+, `/results` is premium per the controller. We
  // request both and let SWR surface the 403 inside `resultsError` so
  // basic users still see their stats.
  const isBasicPlus = useSubscription().tier !== 'free';

  const { data: stats } = useSWR<HedgeStatsResponse>(
    isAuthenticated && isBasicPlus ? '/api/v1/hedge/stats' : null,
    fetchHedgeStats,
  );
  const { data: results } = useSWR<HedgeHistoryResponse>(
    isAuthenticated && isBasicPlus ? '/api/v1/hedge/results' : null,
    fetchHedgeResults,
    { shouldRetryOnError: false },
  );

  if (!isAuthenticated) {
    return (
      <Card>
        <CardBody>
          <p className="text-slate-200">{t('hedge.loginRequired')}</p>
        </CardBody>
      </Card>
    );
  }

  const rows = results?.items?.slice(0, 10) ?? [];

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-slate-100">{t('hedge.history.title')}</h1>
        <p className="text-sm text-slate-400">{t('hedge.history.subtitle')}</p>
      </header>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard
          label={t('hedge.history.stats.totalSettled')}
          value={stats?.totalSettled?.toString() ?? '—'}
        />
        <StatCard
          label={t('hedge.history.stats.winningScenarios')}
          value={stats?.winningScenarios?.toString() ?? '—'}
        />
        <StatCard
          label={t('hedge.history.stats.totalPnl')}
          value={formatYuan(stats?.totalPnl ?? null)}
          tone={profitColor(stats?.totalPnl)}
        />
        <StatCard
          label={t('hedge.history.stats.totalHedgeValueAdded')}
          value={formatYuan(stats?.totalHedgeValueAdded ?? null)}
          tone={profitColor(stats?.totalHedgeValueAdded)}
        />
        <StatCard
          label={t('hedge.history.stats.winRatePct')}
          value={stats?.winRatePct != null ? `${stats.winRatePct.toFixed(2)}%` : '—'}
        />
      </div>

      <Card>
        <CardBody className="overflow-x-auto p-0">
          {rows.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-slate-400">
              {t('hedge.history.noData')}
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="border-b border-slate-800 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-2 text-left">{t('hedge.history.table.scenarioId')}</th>
                  <th className="px-4 py-2 text-left">{t('hedge.history.table.scenarioType')}</th>
                  <th className="px-4 py-2 text-left">{t('hedge.history.table.actualOutcome')}</th>
                  <th className="px-4 py-2 text-right">{t('hedge.history.table.totalPnl')}</th>
                  <th className="px-4 py-2 text-right">
                    {t('hedge.history.table.hedgeValueAdded')}
                  </th>
                  <th className="px-4 py-2 text-right">{t('hedge.history.table.settledAt')}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.scenarioId} className="border-b border-slate-900/80">
                    <td className="px-4 py-2 text-slate-200">#{row.scenarioId}</td>
                    <td className="px-4 py-2 text-slate-300">{row.scenarioType}</td>
                    <td className="px-4 py-2 text-slate-300">{row.actualOutcome}</td>
                    <td
                      className={cn(
                        'px-4 py-2 text-right tabular-nums',
                        profitColor(row.totalPnl),
                      )}
                    >
                      {formatYuan(row.totalPnl)}
                    </td>
                    <td
                      className={cn(
                        'px-4 py-2 text-right tabular-nums',
                        profitColor(row.hedgeValueAdded),
                      )}
                    >
                      {formatYuan(row.hedgeValueAdded)}
                    </td>
                    <td className="px-4 py-2 text-right text-slate-400">
                      {DATE_FMT.format(new Date(row.settledAt))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardBody>
      </Card>

      <p className="text-xs text-slate-500">{HEDGE_DISCLAIMER}</p>
    </div>
  );
}

function StatCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <Card variant="subtle">
      <CardBody>
        <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
        <p className={cn('mt-1 text-xl font-semibold tabular-nums', tone ?? 'text-slate-100')}>
          {value}
        </p>
      </CardBody>
    </Card>
  );
}
