'use client';

import { Check } from 'lucide-react';

import { Button } from '@/components/ui/Button';
import { Card, CardBody } from '@/components/ui/Card';
import { cn, formatPriceCny, formatPriceUsd } from '@/lib/utils';
import type { SubscriptionPlan } from '@/types';

interface PlanCardProps {
  plan: SubscriptionPlan;
  features: string[];
  highlight?: boolean;
  onSelect: (plan: SubscriptionPlan) => void;
  loading?: boolean;
}

export function PlanCard({ plan, features, highlight, onSelect, loading }: PlanCardProps) {
  return (
    <Card
      className={cn(
        'relative flex flex-col',
        highlight && 'border-2 border-brand-500 shadow-[0_0_0_1px_rgba(34,211,238,0.4),0_16px_40px_-16px_rgba(34,211,238,0.45)]',
      )}
    >
      {highlight ? (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-gradient-to-r from-cyan-500 to-amber-400 px-3 py-0.5 text-xs font-bold text-slate-950">
          推荐
        </div>
      ) : null}
      <CardBody className="flex flex-1 flex-col">
        <div className="mb-1 text-xs font-semibold uppercase tracking-wider text-cyan-300">
          {plan.tier}
        </div>
        <div className="mb-1 text-xl font-bold text-slate-100">{plan.displayName}</div>
        <div className="mb-1 flex items-baseline gap-2">
          <span className="hero-number text-4xl font-black tabular-nums">
            {formatPriceUsd(plan.priceUsd)}
          </span>
          <span className="text-sm text-slate-400">/ {plan.durationDays} 天</span>
        </div>
        <div className="mb-5 text-xs text-slate-500">
          支付宝 / 微信 ≈{' '}
          <span className="tabular-nums text-slate-300">
            {formatPriceCny(plan.priceCny)}
          </span>
        </div>
        <ul className="mb-6 flex-1 space-y-2 text-sm text-slate-300">
          {features.map((feature) => (
            <li key={feature} className="flex items-start gap-2">
              <Check size={16} className="mt-0.5 shrink-0 text-cyan-300" />
              <span>{feature}</span>
            </li>
          ))}
        </ul>
        <Button
          variant={highlight ? 'primary' : 'secondary'}
          onClick={() => onSelect(plan)}
          loading={loading}
        >
          立即订阅
        </Button>
      </CardBody>
    </Card>
  );
}
