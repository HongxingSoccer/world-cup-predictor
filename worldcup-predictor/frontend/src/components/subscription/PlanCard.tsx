'use client';

import { Check } from 'lucide-react';

import { Button } from '@/components/ui/Button';
import { Card, CardBody } from '@/components/ui/Card';
import { cn, formatPriceCny } from '@/lib/utils';
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
        highlight && 'border-2 border-brand-600 shadow-xl',
      )}
    >
      {highlight ? (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-brand-600 px-3 py-0.5 text-xs font-bold text-white">
          推荐
        </div>
      ) : null}
      <CardBody className="flex flex-1 flex-col">
        <div className="mb-1 text-sm font-semibold uppercase tracking-wider text-brand-600">
          {plan.tier}
        </div>
        <div className="mb-1 text-xl font-bold text-slate-100">{plan.displayName}</div>
        <div className="mb-4 flex items-baseline gap-2">
          <span className="text-3xl font-black text-slate-100">{formatPriceCny(plan.priceCny)}</span>
          <span className="text-sm text-slate-400">/ {plan.durationDays} 天</span>
        </div>
        <ul className="mb-6 flex-1 space-y-2 text-sm text-slate-300">
          {features.map((feature) => (
            <li key={feature} className="flex items-start gap-2">
              <Check size={16} className="mt-0.5 shrink-0 text-brand-600" />
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
