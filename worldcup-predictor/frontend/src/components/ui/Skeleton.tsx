import type { HTMLAttributes } from 'react';

import { cn } from '@/lib/utils';

/**
 * Pulsing placeholder rectangle. Use as `<Skeleton className="h-4 w-32" />`
 * — the consumer always supplies the dimensions so the surrounding layout
 * doesn't shift when the real content lands.
 */
export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('animate-pulse rounded-md bg-slate-700/70', className)}
      {...props}
    />
  );
}

/** Pre-baked card-shaped skeleton for match list / track-record placeholders. */
export function SkeletonCard() {
  return (
    <div className="space-y-3 rounded-2xl surface-card p-5 shadow-sm">
      <Skeleton className="h-4 w-32" />
      <Skeleton className="h-6 w-full" />
      <Skeleton className="h-3 w-3/4" />
    </div>
  );
}
