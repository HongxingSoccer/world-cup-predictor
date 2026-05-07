'use client';

import { CreditCard, Globe2, Smartphone, Wallet } from 'lucide-react';
import { useEffect, useState } from 'react';

import { PlanCard } from '@/components/subscription/PlanCard';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { useT } from '@/i18n/I18nProvider';
import { apiGet, apiPost } from '@/lib/api';
import { cn, formatPriceCny, formatPriceUsd } from '@/lib/utils';
import type { PaymentInitResponse, SubscriptionPlan } from '@/types';

type PaymentChannel = 'alipay' | 'wechat_pay' | 'stripe';

const CNY_CHANNELS: ReadonlySet<PaymentChannel> = new Set(['alipay', 'wechat_pay']);

interface FeatureGroups {
  basic: string[];
  premium: string[];
}

// Fallback plans used while the catalogue is loading or if the API fails.
// Mirrors the Java SubscriptionService.PLAN_CATALOGUE numbers exactly.
const FALLBACK_PLANS: SubscriptionPlan[] = [
  { tier: 'basic',   planType: 'monthly',        priceUsd:  999, priceCny:  7193, durationDays: 30, displayName: 'Basic · Monthly' },
  { tier: 'basic',   planType: 'worldcup_pass',  priceUsd: 2999, priceCny: 21593, durationDays: 60, displayName: 'Basic · World-Cup Pass' },
  { tier: 'premium', planType: 'monthly',        priceUsd: 1999, priceCny: 14393, durationDays: 30, displayName: 'Premium · Monthly' },
  { tier: 'premium', planType: 'worldcup_pass',  priceUsd: 4999, priceCny: 35993, durationDays: 60, displayName: 'Premium · World-Cup Pass' },
];

export function SubscribePageClient() {
  const t = useT();
  const [plans, setPlans] = useState<SubscriptionPlan[]>(FALLBACK_PLANS);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [channel, setChannel] = useState<PaymentChannel>('alipay');
  const [orderResult, setOrderResult] = useState<PaymentInitResponse | null>(null);

  // Feature lists are i18n-derived so they switch with locale. Keys live in
  // subscription.features.* below; falling back to zh strings so this page
  // still works if a key is missing.
  const FEATURES: FeatureGroups = {
    basic: [
      t('subscription.features.basic1', '完整 1x2 胜平负概率'),
      t('subscription.features.basic2', '比分概率 Top10 + 10×10 矩阵'),
      t('subscription.features.basic3', '大小球 / BTTS 预测'),
      t('subscription.features.basic4', '赔率 EV 分析 + 价值信号'),
    ],
    premium: [
      t('subscription.features.premium1', '包含 Basic 全部权益'),
      t('subscription.features.premium2', 'xG / 伤病情报面板'),
      t('subscription.features.premium3', '置信度筛选器'),
      t('subscription.features.premium4', '世界杯通票优先权'),
    ],
  };

  useEffect(() => {
    let cancelled = false;
    apiGet<SubscriptionPlan[]>('/api/v1/subscriptions/plans')
      .then((rows) => {
        if (cancelled || !Array.isArray(rows) || rows.length === 0) return;
        setPlans(rows);
      })
      .catch(() => undefined);
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
        <h1 className="text-2xl font-bold text-slate-100">{t('subscription.title')}</h1>
        <p className="mt-1 text-sm text-slate-400">{t('subscription.priceNote')}</p>
      </div>

      <ChannelPicker value={channel} onChange={setChannel} />

      <div className="grid gap-4 md:grid-cols-2">
        {plans.map((plan) => {
          const key = `${plan.tier}-${plan.planType}`;
          const features = FEATURES[plan.tier];
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
          <h2 className="text-base font-semibold text-slate-100">{t('subscription.faq')}</h2>
        </CardHeader>
        <CardBody className="space-y-3 text-sm text-slate-300">
          <Faq q={t('subscription.faqQ1')} a={t('subscription.faqA1')} />
          <Faq q={t('subscription.faqQ2')} a={t('subscription.faqA2')} />
          <Faq q={t('subscription.faqQ3')} a={t('subscription.faqA3')} />
          <Faq q={t('subscription.faqQ4')} a={t('subscription.faqA4')} />
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
  const t = useT();
  const channels: Array<{
    id: PaymentChannel;
    label: string;
    detail: string;
    icon: typeof Wallet;
  }> = [
    {
      id: 'alipay',
      label: t('subscription.paymentAlipay'),
      detail: t('subscription.paymentCnySettlement'),
      icon: Wallet,
    },
    {
      id: 'wechat_pay',
      label: t('subscription.paymentWechat'),
      detail: t('subscription.paymentCnySettlement'),
      icon: Smartphone,
    },
    {
      id: 'stripe',
      label: t('subscription.paymentStripe'),
      detail: t('subscription.paymentUsdSettlement'),
      icon: Globe2,
    },
  ];
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-slate-400">
        <CreditCard size={12} />
        {t('subscription.paymentMethod')}
      </div>
      <div className="grid gap-2 sm:grid-cols-3">
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
  const t = useT();
  const channelLabel =
    result.paymentChannel === 'alipay'
      ? t('subscription.paymentAlipay')
      : result.paymentChannel === 'wechat_pay'
        ? t('subscription.paymentWechat')
        : t('subscription.paymentStripe');
  // International channels charge USD natively. CNY is mirrored on the row
  // for ledger continuity but isn't what the user actually pays.
  const cnyChannel = CNY_CHANNELS.has(result.paymentChannel as PaymentChannel);
  return (
    <Card>
      <CardHeader>
        <h2 className="text-base font-semibold text-slate-100">{t('subscription.orderCreated')}</h2>
        <span className="text-xs text-slate-400">{t('subscription.orderDemo')}</span>
      </CardHeader>
      <CardBody className="space-y-2 text-sm">
        <div className="flex items-center justify-between">
          <span className="text-slate-400">{t('subscription.orderNo')}</span>
          <span className="font-mono text-xs tabular-nums text-slate-100">
            {result.orderNo}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-slate-400">{t('subscription.paymentMethod')}</span>
          <span className="text-slate-100">{channelLabel}</span>
        </div>
        {cnyChannel ? (
          <>
            <div className="flex items-center justify-between">
              <span className="text-slate-400">{t('subscription.displayAmount')}</span>
              <span className="font-semibold tabular-nums text-slate-100">
                {formatPriceUsd(result.amountUsd)}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-400">{t('subscription.actualAmount')}</span>
              <span className="font-semibold tabular-nums text-cyan-300">
                {formatPriceCny(result.amountCny)}
              </span>
            </div>
          </>
        ) : (
          <div className="flex items-center justify-between">
            <span className="text-slate-400">{t('subscription.actualAmount')}</span>
            <span className="font-semibold tabular-nums text-cyan-300">
              {formatPriceUsd(result.amountUsd)}
            </span>
          </div>
        )}
        <p className="mt-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
          {t('subscription.orderNote')}
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
