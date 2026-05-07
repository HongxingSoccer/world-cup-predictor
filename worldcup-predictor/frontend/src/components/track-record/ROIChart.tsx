'use client';

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { Card, CardBody, CardHeader } from '@/components/ui/Card';

export interface RoiPoint {
  date: string;       // 'YYYY-MM-DD'
  cumulativePnl: number;
}

interface ROIChartProps {
  series: RoiPoint[];
}

/**
 * Cumulative P&L line chart. Recharts is theme-blind, so axis / grid / line
 * colors are inlined to match the dark slate palette.
 */
export function ROIChart({ series }: ROIChartProps) {
  return (
    <Card>
      <CardHeader>
        <h3 className="text-sm font-semibold text-slate-100">ROI 累计曲线</h3>
        <span className="text-xs text-slate-400">单位下注，按日累计</span>
      </CardHeader>
      <CardBody>
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={series} margin={{ top: 10, right: 16, bottom: 0, left: -10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fill: '#94a3b8' }}
                stroke="#475569"
                minTickGap={32}
              />
              <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} stroke="#475569" />
              <Tooltip
                formatter={(value: number) => [`${value.toFixed(2)} 单位`, '累计 P&L']}
                contentStyle={{
                  borderRadius: 12,
                  border: '1px solid rgba(34, 211, 238, 0.35)',
                  backgroundColor: 'rgba(15, 23, 42, 0.92)',
                  color: '#e2e8f0',
                  boxShadow: '0 16px 32px -16px rgba(0, 0, 0, 0.6)',
                }}
                labelStyle={{ color: '#94a3b8', fontSize: 11 }}
                itemStyle={{ color: '#22d3ee' }}
              />
              <Line
                type="monotone"
                dataKey="cumulativePnl"
                stroke="#22d3ee"
                strokeWidth={2.4}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardBody>
    </Card>
  );
}
