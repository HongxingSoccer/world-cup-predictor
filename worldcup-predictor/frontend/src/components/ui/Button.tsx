import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';

import { cn } from '@/lib/utils';

type Variant = 'primary' | 'secondary' | 'ghost' | 'destructive';
type Size = 'sm' | 'md' | 'lg';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  leftIcon?: ReactNode;
}

const VARIANT_STYLES: Record<Variant, string> = {
  primary:
    'bg-brand-500 text-slate-950 hover:bg-brand-400 disabled:bg-slate-700 disabled:text-slate-500 shadow-[0_8px_24px_-12px_rgba(34,211,238,0.6)]',
  secondary:
    'bg-slate-800/80 text-slate-100 hover:bg-slate-700 border border-slate-700 disabled:bg-slate-900 disabled:text-slate-600',
  ghost:
    'bg-transparent text-slate-300 hover:bg-slate-800/60 disabled:text-slate-600',
  destructive:
    'bg-rose-500 text-white hover:bg-rose-400 disabled:bg-rose-900 disabled:text-rose-700',
};

const SIZE_STYLES: Record<Size, string> = {
  sm: 'h-8 px-3 text-sm',
  md: 'h-10 px-4 text-sm',
  lg: 'h-12 px-6 text-base',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = 'primary', size = 'md', loading, leftIcon, className, children, disabled, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-xl font-semibold',
        'transition-colors duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500',
        'disabled:cursor-not-allowed',
        VARIANT_STYLES[variant],
        SIZE_STYLES[size],
        className,
      )}
      {...props}
    >
      {loading ? (
        <span
          className="h-4 w-4 animate-spin rounded-full border-2 border-current border-r-transparent"
          aria-hidden
        />
      ) : (
        leftIcon
      )}
      {children}
    </button>
  );
});
