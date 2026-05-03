'use client';

import { cn } from '@/lib/utils';

interface CompetitionFilterProps {
  options: string[];
  value: string | null;
  onChange: (value: string | null) => void;
}

export function CompetitionFilter({ options, value, onChange }: CompetitionFilterProps) {
  if (options.length === 0) return null;
  return (
    <div className="flex gap-2 overflow-x-auto py-2">
      <Pill active={value === null} onClick={() => onChange(null)}>
        全部
      </Pill>
      {options.map((opt) => (
        <Pill key={opt} active={value === opt} onClick={() => onChange(opt)}>
          {opt}
        </Pill>
      ))}
    </div>
  );
}

function Pill({
  active,
  children,
  onClick,
}: {
  active: boolean;
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'shrink-0 rounded-full border px-3 py-1 text-xs font-medium',
        active
          ? 'border-brand-600 bg-brand-600 text-white'
          : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50',
      )}
    >
      {children}
    </button>
  );
}
