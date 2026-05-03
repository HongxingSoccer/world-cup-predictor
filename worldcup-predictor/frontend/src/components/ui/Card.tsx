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
        'rounded-2xl bg-white text-slate-900',
        variant === 'default' && 'border border-slate-200 shadow-sm',
        variant === 'subtle' && 'bg-slate-50',
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
        'flex items-start justify-between gap-3 border-b border-slate-100 px-5 py-4',
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
      className={cn('border-t border-slate-100 px-5 py-3 text-sm text-slate-500', className)}
    >
      {children}
    </div>
  );
}
