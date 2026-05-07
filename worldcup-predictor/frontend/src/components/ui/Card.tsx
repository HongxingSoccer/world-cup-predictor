import type { HTMLAttributes, ReactNode } from 'react';

import { cn } from '@/lib/utils';

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  /** Removes the default border + softens the surface for nested cards. */
  variant?: 'default' | 'subtle';
}

export function Card({ children, className, variant = 'default', ...props }: CardProps) {
  return (
    <div
      className={cn(
        'rounded-2xl text-slate-100',
        // surface-card from globals.css: glassy slate-900/60 with a hairline
        // border that lifts to cyan on hover. variant=subtle drops the hover
        // glow for nested / secondary cards so the parent stays the focus.
        variant === 'default' && 'surface-card',
        variant === 'subtle' &&
          'border border-slate-800/70 bg-slate-900/40 backdrop-blur-sm',
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        'flex items-start justify-between gap-3 border-b border-slate-800/70 px-5 py-4',
        className,
      )}
    >
      {children}
    </div>
  );
}

export function CardBody({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('px-5 py-4', className)}>{children}</div>;
}

export function CardFooter({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        'border-t border-slate-800/70 px-5 py-3 text-sm text-slate-400',
        className,
      )}
    >
      {children}
    </div>
  );
}
