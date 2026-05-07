import type { HTMLAttributes, ReactNode } from 'react';

import { cn } from '@/lib/utils';

type Tone = 'neutral' | 'success' | 'warning' | 'danger' | 'info';

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
  children: ReactNode;
}

const TONES: Record<Tone, string> = {
  neutral: 'bg-slate-800/70 text-slate-300 border-slate-700',
  success: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  warning: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  danger:  'bg-rose-500/15 text-rose-300 border-rose-500/30',
  info:    'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
};

export function Badge({ tone = 'neutral', children, className, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium',
        TONES[tone],
        className,
      )}
      {...props}
    >
      {children}
    </span>
  );
}
