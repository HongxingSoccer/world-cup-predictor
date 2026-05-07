'use client';

import { cn } from '@/lib/utils';

export interface TabItem<T extends string> {
  id: T;
  label: string;
  count?: number | null;
  disabled?: boolean;
}

interface TabsProps<T extends string> {
  value: T;
  items: ReadonlyArray<TabItem<T>>;
  onChange: (id: T) => void;
  className?: string;
}

/**
 * Minimal segmented-control style tabs. Cyan underline on the active tab,
 * subtle slate-800 separator. Designed to slot above a list/grid; emits a
 * controlled value back via onChange.
 */
export function Tabs<T extends string>({ value, items, onChange, className }: TabsProps<T>) {
  return (
    <div
      role="tablist"
      className={cn(
        'flex items-center gap-1 border-b border-slate-800/70',
        className,
      )}
    >
      {items.map((item) => {
        const active = value === item.id;
        return (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={active}
            disabled={item.disabled}
            onClick={() => onChange(item.id)}
            className={cn(
              'relative inline-flex items-center gap-2 px-3 py-2 text-sm font-medium transition-colors',
              'disabled:cursor-not-allowed disabled:text-slate-600',
              active
                ? 'text-cyan-300'
                : 'text-slate-400 hover:text-slate-200',
            )}
          >
            <span>{item.label}</span>
            {item.count !== undefined && item.count !== null ? (
              <span
                className={cn(
                  'rounded-full px-1.5 text-[10px] tabular-nums',
                  active
                    ? 'bg-cyan-500/20 text-cyan-200'
                    : 'bg-slate-800 text-slate-400',
                )}
              >
                {item.count}
              </span>
            ) : null}
            {active ? (
              <span
                aria-hidden
                className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-gradient-to-r from-cyan-400 to-amber-400"
              />
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
