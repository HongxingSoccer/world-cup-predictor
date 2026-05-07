'use client';

import { Lock } from 'lucide-react';
import Link from 'next/link';
import type { ReactNode } from 'react';

import { Button } from '@/components/ui/Button';
import { useSubscription } from '@/hooks/useSubscription';
import { cn } from '@/lib/utils';
import type { FeatureKey } from '@/stores/subscription-store';

interface PaywallOverlayProps {
  feature: FeatureKey;
  /** Friendly text shown to free users (e.g. "比分概率矩阵"). */
  featureLabel: string;
  children: ReactNode;
  /** Override the default "解锁查看完整分析" CTA. */
  ctaText?: string;
  className?: string;
}

/**
 * Wrap any paid block with `<PaywallOverlay feature="...">`. When the user's
 * tier doesn't cover the feature, the children are blurred + a centered card
 * prompts the upgrade. When access is granted, children render unchanged.
 */
export function PaywallOverlay({
  feature,
  featureLabel,
  children,
  ctaText,
  className,
}: PaywallOverlayProps) {
  const { canAccess } = useSubscription();
  if (canAccess(feature)) {
    return <div className={className}>{children}</div>;
  }

  return (
    <div className={cn('relative', className)}>
      <div className="pointer-events-none select-none blur-[6px]" aria-hidden>
        {children}
      </div>
      <div className="absolute inset-0 flex items-center justify-center p-6">
        <div className="surface-card rounded-2xl p-5 text-center shadow-2xl">
          <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full border border-accent-500/40 bg-accent-500/15 text-accent-400">
            <Lock size={18} />
          </div>
          <div className="mb-1 text-sm font-semibold text-slate-100">
            {featureLabel}
          </div>
          <div className="mb-4 text-xs text-slate-400">
            订阅后可查看完整分析。基础版 $9.99/月起。
          </div>
          <Link href="/subscribe">
            <Button size="sm">{ctaText ?? '解锁查看完整分析'}</Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
