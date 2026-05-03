'use client';

import { useState } from 'react';

import { PlanCard } from '@/components/subscription/PlanCard';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { apiPost } from '@/lib/api';
import type { PaymentInitResponse, SubscriptionPlan } from '@/types';

const PLANS: SubscriptionPlan[] = [
  { tier: 'basic',   planType: 'monthly',       priceCny: 2990,  durationDays: 30, displayName: 'Basic · 月度' },
  { tier: 'basic',   planType: 'worldcup_pass', priceCny: 6800,  durationDays: 60, displayName: 'Basic · 世界杯通票' },
  { tier: 'premium', planType: 'monthly',       priceCny: 5990,  durationDays: 30, displayName: 'Premium · 月度' },
  { tier: 'premium', planType: 'worldcup_pass', priceCny: 12800, durationDays: 60, displayName: 'Premium · 世界杯通票' },
];

const FEATURE_GROUPS: Record<'basic' | 'premium', string[]> = {
  basic: [
    '完整 1x2 胜平负概率',
    '比分概率 Top10 + 10×10 矩阵',
    '大小球 / BTTS 预测',
    '赔率 EV 分析 + 价值信号',
  ],
  premium: [
    '包含 Basic 全部权益',
    'xG / 伤病情报面板',
    '置信度筛选器',
    '世界杯通票优先权',
  ],
};

export function SubscribePageClient() {
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const onSelect = async (plan: SubscriptionPlan) => {
    const key = `${plan.tier}-${plan.planType}`;
    setBusyKey(key);
    try {
      const init = await apiPost<PaymentInitResponse>('/api/v1/subscriptions/create', {
        tier: plan.tier,
        planType: plan.planType,
        paymentChannel: 'alipay',
      });
      // Phase 3.5: hand the SDK params off to the Alipay / WeChat client SDK.
      window.alert(`已创建订单 ${init.orderNo} (¥${(init.amountCny / 100).toFixed(2)})`);
    } catch (err) {
      const message = err instanceof Error ? err.message : '订阅创建失败';
      window.alert(message);
    } finally {
      setBusyKey(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="text-center">
        <h1 className="text-2xl font-bold text-slate-900">解锁完整 AI 预测</h1>
        <p className="mt-1 text-sm text-slate-500">
          世界杯期间限时优惠，通票更划算。
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {PLANS.map((plan) => {
          const key = `${plan.tier}-${plan.planType}`;
          const features = FEATURE_GROUPS[plan.tier];
          return (
            <PlanCard
              key={key}
              plan={plan}
              features={features}
              highlight={plan.planType === 'worldcup_pass'}
              onSelect={onSelect}
              loading={busyKey === key}
            />
          );
        })}
      </div>

      <Card>
        <CardHeader>
          <h2 className="text-base font-semibold text-slate-900">常见问题</h2>
        </CardHeader>
        <CardBody className="space-y-3 text-sm text-slate-700">
          <Faq
            q="可以随时取消吗？"
            a="可以。订阅默认不开启自动续费；月度订阅到期后自动转回免费版。"
          />
          <Faq
            q="世界杯通票包含哪些内容？"
            a="世界杯期间所有比赛的完整 AI 预测、赔率分析、价值信号、xG 与伤病情报。"
          />
          <Faq
            q="支付方式？"
            a="支持支付宝和微信支付。"
          />
        </CardBody>
      </Card>
    </div>
  );
}

function Faq({ q, a }: { q: string; a: string }) {
  return (
    <div>
      <div className="font-semibold text-slate-900">Q · {q}</div>
      <div className="text-slate-600">A · {a}</div>
    </div>
  );
}
