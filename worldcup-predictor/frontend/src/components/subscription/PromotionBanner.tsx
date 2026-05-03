'use client';

import { Sparkles } from 'lucide-react';
import Link from 'next/link';

import { useSubscription } from '@/hooks/useSubscription';

/** Bottom-of-page promo for free users only. Hides itself for paying users. */
export function PromotionBanner() {
  const { tier } = useSubscription();
  if (tier !== 'free') return null;

  return (
    <Link
      href="/subscribe"
      className="block rounded-2xl bg-gradient-to-r from-brand-600 to-emerald-500 p-5 text-white shadow-lg transition hover:shadow-xl"
    >
      <div className="flex items-center gap-3">
        <Sparkles size={22} />
        <div className="flex-1">
          <div className="text-base font-bold">解锁完整 AI 预测</div>
          <div className="text-sm opacity-90">
            比分矩阵 · 赔率 EV 分析 · 价值信号 — 基础版仅 ¥29.9/月起
          </div>
        </div>
        <span className="hidden rounded-full bg-white/20 px-3 py-1 text-xs font-semibold sm:inline-block">
          立即开通 →
        </span>
      </div>
    </Link>
  );
}
