'use client';

import { CreditCard, Smartphone, Wallet } from 'lucide-react';
import { useEffect, useState } from 'react';

import { PlanCard } from '@/components/subscription/PlanCard';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { apiGet, apiPost } from '@/lib/api';
import { cn, formatPriceCny, formatPriceUsd } from '@/lib/utils';
import type { PaymentInitResponse, SubscriptionPlan } from '@/types';

type PaymentChannel = 'alipay' | 'wechat_pay';

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

// Fallback plans used while the catalogue is loading or if the API fails.
// Mirrors the Java SubscriptionService.PLAN_CATALOGUE numbers exactly.
const FALLBACK_PLANS: SubscriptionPlan[] = [
  { tier: 'basic',   planType: 'monthly',        priceUsd:  999, priceCny:  7193, durationDays: 30, displayName: 'Basic · 月度' },
  { tier: 'basic',   planType: 'worldcup_pass',  priceUsd: 2999, priceCny: 21593, durationDays: 60, displayName: 'Basic · 世界杯通票' },
  { tier: 'premium', planType: 'monthly',        priceUsd: 1999, priceCny: 14393, durationDays: 30, displayName: 'Premium · 月度' },
  { tier: 'premium', planType: 'worldcup_pass',  priceUsd: 4999, priceCny: 35993, durationDays: 60, displayName: 'Premium · 世界杯通票' },
];

export function SubscribePageClient() {
  const [plans, setPlans] = useState<SubscriptionPlan[]>(FALLBACK_PLANS);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [channel, setChannel] = useState<PaymentChannel>('alipay');
  const [orderResult, setOrderResult] = useState<PaymentInitResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiGet<SubscriptionPlan[]>('/api/v1/subscriptions/plans')
      .then((rows) => {
        if (cancelled || !Array.isArray(rows) || rows.length === 0) return;
        setPlans(rows);
      })
      .catch(() => {
        // Stick with the fallback catalogue; the page is still usable.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const onSelect = async (plan: SubscriptionPlan) => {
    const key = `${plan.tier}-${plan.planType}`;
    setBusyKey(key);
    setOrderResult(null);
    try {
      const init = await apiPost<PaymentInitResponse>('/api/v1/subscriptions/create', {
        tier: plan.tier,
        planType: plan.planType,
        paymentChannel: channel,
      });
      setOrderResult(init);
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
        <h1 className="text-2xl font-bold text-slate-100">解锁完整 AI 预测</h1>
        <p className="mt-1 text-sm text-slate-400">
          所有价格以美元计价。支付宝 / 微信支付按当日汇率结算为人民币。
        </p>
      </div>

      <ChannelPicker value={channel} onChange={setChannel} />

      <div className="grid gap-4 md:grid-cols-2">
        {plans.map((plan) => {
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

      {orderResult ? <OrderConfirmation result={orderResult} /> : null}

      <Card>
        <CardHeader>
          <h2 className="text-base font-semibold text-slate-100">常见问题</h2>
        </CardHeader>
        <CardBody className="space-y-3 text-sm text-slate-300">
          <Faq
            q="为什么显示美元，付款时是人民币？"
            a="平台以美元为基准定价，方便国际用户对照。中国大陆用户使用支付宝 / 微信支付时，按下单时的汇率结算为人民币（参考 1 USD ≈ 7.20 CNY）。"
          />
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
            a="当前支持支付宝 / 微信支付（人民币）。后续将支持 Stripe / Apple Pay / Google Pay 直接美元结算。"
          />
        </CardBody>
      </Card>
    </div>
  );
}

interface ChannelPickerProps {
  value: PaymentChannel;
  onChange: (v: PaymentChannel) => void;
}

function ChannelPicker({ value, onChange }: ChannelPickerProps) {
  const channels: Array<{
    id: PaymentChannel;
    label: string;
    detail: string;
    icon: typeof Wallet;
  }> = [
    {
      id: 'alipay',
      label: '支付宝',
      detail: '人民币结算',
      icon: Wallet,
    },
    {
      id: 'wechat_pay',
      label: '微信支付',
      detail: '人民币结算',
      icon: Smartphone,
    },
  ];
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-slate-400">
        <CreditCard size={12} />
        支付方式
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {channels.map(({ id, label, detail, icon: Icon }) => {
          const active = value === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => onChange(id)}
              className={cn(
                'flex items-center gap-3 rounded-xl border px-3 py-3 text-left transition-colors',
                active
                  ? 'border-cyan-500/40 bg-cyan-500/10 text-slate-100'
                  : 'border-slate-800/70 bg-slate-900/40 text-slate-300 hover:border-slate-700',
              )}
            >
              <span
                className={cn(
                  'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg',
                  active ? 'bg-cyan-500/20 text-cyan-300' : 'bg-slate-800/80 text-slate-400',
                )}
              >
                <Icon size={18} />
              </span>
              <div className="flex-1">
                <div className="text-sm font-semibold">{label}</div>
                <div className="text-xs text-slate-400">{detail}</div>
              </div>
              <span
                className={cn(
                  'h-4 w-4 rounded-full border-2',
                  active ? 'border-cyan-300 bg-cyan-300' : 'border-slate-700',
                )}
              />
            </button>
          );
        })}
      </div>
    </div>
  );
}

function OrderConfirmation({ result }: { result: PaymentInitResponse }) {
  const channelLabel =
    result.paymentChannel === 'alipay' ? '支付宝' : '微信支付';
  return (
    <Card>
      <CardHeader>
        <h2 className="text-base font-semibold text-slate-100">订单已生成</h2>
        <span className="text-xs text-slate-400">演练（payment SDK 待接入）</span>
      </CardHeader>
      <CardBody className="space-y-2 text-sm">
        <div className="flex items-center justify-between">
          <span className="text-slate-400">订单号</span>
          <span className="font-mono text-xs tabular-nums text-slate-100">
            {result.orderNo}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-slate-400">支付方式</span>
          <span className="text-slate-100">{channelLabel}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-slate-400">显示金额</span>
          <span className="font-semibold tabular-nums text-slate-100">
            {formatPriceUsd(result.amountUsd)}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-slate-400">实付金额</span>
          <span className="font-semibold tabular-nums text-cyan-300">
            {formatPriceCny(result.amountCny)}
          </span>
        </div>
        <p className="mt-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
          支付 SDK 将在下个迭代接入；当前展示用以验证下单流水。
        </p>
      </CardBody>
    </Card>
  );
}

function Faq({ q, a }: { q: string; a: string }) {
  return (
    <div>
      <div className="font-semibold text-slate-100">Q · {q}</div>
      <div className="text-slate-400">A · {a}</div>
    </div>
  );
}
