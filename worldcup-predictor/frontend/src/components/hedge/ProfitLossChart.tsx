'use client';

import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { useT } from '@/i18n/I18nProvider';

interface Props {
  profitIfOriginalWins: number;
  profitIfHedgeWins: number;
  maxLoss: number;
}

/**
 * Three-bar chart of P/L across the two outcomes + the worst-case-loss
 * floor. Positives are green, negatives rose, zero is slate.
 */
export function ProfitLossChart({
  profitIfOriginalWins,
  profitIfHedgeWins,
  maxLoss,
}: Props) {
  const t = useT();

  const data = [
    { key: 'orig', name: t('hedge.result.chartProfitOrig'), value: profitIfOriginalWins },
    { key: 'hedge', name: t('hedge.result.chartProfitHedge'), value: profitIfHedgeWins },
    { key: 'loss', name: t('hedge.result.chartMaxLoss'), value: maxLoss },
  ];

  return (
    <div className="h-48 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 10, right: 12, bottom: 6, left: 0 }}>
          <XAxis
            dataKey="name"
            tick={{ fill: '#94a3b8', fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: '#1e293b' }}
          />
          <YAxis
            tick={{ fill: '#94a3b8', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v: number) => `¥${v}`}
          />
          <Tooltip
            cursor={{ fill: 'rgba(148, 163, 184, 0.08)' }}
            contentStyle={{
              background: '#0f172a',
              border: '1px solid #1e293b',
              borderRadius: 8,
              fontSize: 12,
              color: '#e2e8f0',
            }}
            formatter={(value: number) => [`¥${value.toFixed(2)}`, '']}
            labelFormatter={(label: string) => label}
          />
          <Bar dataKey="value" radius={[4, 4, 0, 0]}>
            {data.map((entry) => (
              <Cell
                key={entry.key}
                fill={
                  entry.value > 0
                    ? '#10b981'
                    : entry.value < 0
                      ? '#ef4444'
                      : '#94a3b8'
                }
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
