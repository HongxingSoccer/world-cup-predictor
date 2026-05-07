'use client';

import { ChevronLeft, ChevronRight } from 'lucide-react';
import { useRouter, useSearchParams } from 'next/navigation';

import { Button } from '@/components/ui/Button';

/** Helper: format/shift a YYYY-MM-DD string by `delta` days. */
function shiftDate(iso: string, delta: number): string {
  const date = new Date(`${iso}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + delta);
  return date.toISOString().slice(0, 10);
}

interface MatchDayHeaderProps {
  /** YYYY-MM-DD; defaults to today. */
  date?: string;
}

export function MatchDayHeader({ date }: MatchDayHeaderProps) {
  const router = useRouter();
  const params = useSearchParams();
  const current = date ?? params.get('date') ?? new Date().toISOString().slice(0, 10);

  const navigate = (delta: number) => {
    const next = shiftDate(current, delta);
    router.push(`/?date=${next}`);
  };

  return (
    <div className="flex items-center justify-between gap-3 rounded-2xl surface-card px-3 py-2">
      <Button variant="ghost" size="sm" onClick={() => navigate(-1)} aria-label="前一天">
        <ChevronLeft size={18} />
      </Button>
      <div className="flex flex-col items-center">
        <div className="text-sm font-semibold text-slate-100">{current}</div>
        <div className="text-xs text-slate-400">UTC</div>
      </div>
      <Button variant="ghost" size="sm" onClick={() => navigate(1)} aria-label="后一天">
        <ChevronRight size={18} />
      </Button>
    </div>
  );
}
