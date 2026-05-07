'use client';

import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { useT } from '@/i18n/I18nProvider';

interface StatRow {
  label: string;
  // Snake or camel — accepting both because Java forwards the Python
  // list-of-maps as-is, preserving snake_case from the ml-api response.
  labelKey?: string | null;
  label_key?: string | null;
  home: number | string;
  away: number | string;
}

interface TeamStatsPanelProps {
  homeTeam: string;
  awayTeam: string;
  rows: StatRow[];
}

export function TeamStatsPanel({ homeTeam, awayTeam, rows }: TeamStatsPanelProps) {
  const t = useT();
  return (
    <Card>
      <CardHeader>
        <h3 className="text-sm font-semibold text-slate-100">{t('match.statsCompare')}</h3>
      </CardHeader>
      <CardBody>
        <div className="mb-2 grid grid-cols-3 text-xs uppercase tracking-wider text-slate-400">
          <div className="text-right">{homeTeam}</div>
          <div className="text-center">{t('match.metrics')}</div>
          <div className="text-left">{awayTeam}</div>
        </div>
        {rows.length === 0 ? (
          <div className="py-6 text-center text-sm text-slate-500">{t('match.noRecentStats')}</div>
        ) : (
          <div className="divide-y divide-slate-800/70">
            {rows.map((row) => (
              <div key={row.label} className="grid grid-cols-3 items-center py-2 text-sm">
                <div className="text-right font-semibold tabular-nums text-slate-100">
                  {row.home}
                </div>
                <div className="text-center text-slate-400">
                  {(() => {
                    const key = row.labelKey ?? row.label_key;
                    return key ? t(key, row.label) : row.label;
                  })()}
                </div>
                <div className="text-left font-semibold tabular-nums text-slate-100">
                  {row.away}
                </div>
              </div>
            ))}
          </div>
        )}
      </CardBody>
    </Card>
  );
}
