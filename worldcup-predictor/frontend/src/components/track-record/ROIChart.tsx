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
 * Simple cumulative P&L line chart. The Phase-3 backend supplies the
 * `(date, cumulativePnl)` series via /api/v1/track-record/roi-chart.
 */
export function ROIChart({ series }: ROIChartProps) {
  return (
    <Card>
      <CardHeader>
        <h3 className="text-sm font-semibold text-slate-900">ROI 累计曲线</h3>
        <span className="text-xs text-slate-500">单位下注，按日累计</span>
      </CardHeader>
      <CardBody>
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={series} margin={{ top: 10, right: 16, bottom: 0, left: -10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} stroke="#94a3b8" minTickGap={32} />
              <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" />
              <Tooltip
                formatter={(value: number) => [`${value.toFixed(2)} 单位`, '累计 P&L']}
                contentStyle={{ borderRadius: 12, border: '1px solid #e2e8f0' }}
              />
              <Line
                type="monotone"
                dataKey="cumulativePnl"
                stroke="#16a34a"
                strokeWidth={2}
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
