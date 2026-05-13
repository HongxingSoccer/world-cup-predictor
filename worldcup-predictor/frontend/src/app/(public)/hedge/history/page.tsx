import type { Metadata } from 'next';

import { HedgeHistoryList } from '@/components/hedge/HedgeHistoryList';

export const dynamic = 'force-dynamic';

export const metadata: Metadata = {
  title: '对冲历史 · WCP',
  description: '已结算对冲场景的综合统计 + 最近 10 条记录。',
  robots: { index: false, follow: false },
};

export default function HedgeHistoryPage() {
  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <HedgeHistoryList />
    </main>
  );
}
