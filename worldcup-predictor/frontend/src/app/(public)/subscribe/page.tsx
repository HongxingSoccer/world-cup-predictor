import type { Metadata } from 'next';

import { SubscribePageClient } from './SubscribePageClient';

export const metadata: Metadata = {
  title: '订阅 · 解锁完整 AI 预测',
  description: '基础版 $9.99/月起，世界杯通票 $29.99 起。AI 比分概率 · 赔率价值分析 · 高价值推荐。',
};

export default function SubscribePage() {
  return <SubscribePageClient />;
}
