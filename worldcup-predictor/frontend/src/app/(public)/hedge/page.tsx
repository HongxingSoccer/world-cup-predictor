import type { Metadata } from 'next';

import { HedgeCalculator } from '@/components/hedge/HedgeCalculator';

// Same reason as the homepage / track-record page: ISR strips the
// cookie-driven locale at build time, so force-dynamic preserves the
// per-request locale resolution and the JWT-bearer-required auth state.
export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: '对冲计算器 · WCP',
  description:
    '基于 ML 模型 + 实时赔率的对冲方案计算器,支持单场和串关。仅供数据分析参考。',
  robots: { index: false, follow: false }, // premium-gated content
};

export default function HedgePage() {
  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <HedgeCalculator />
    </main>
  );
}
