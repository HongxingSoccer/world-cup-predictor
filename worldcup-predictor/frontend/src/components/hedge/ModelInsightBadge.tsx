'use client';

import { Info } from 'lucide-react';

import { useT } from '@/i18n/I18nProvider';
import { cn } from '@/lib/utils';
import type { AssessmentLabel } from '@/types/hedge';

interface Props {
  assessment: AssessmentLabel | null;
}

/**
 * Pill badge for the advisor verdict. 4 valid strings + `null` (model
 * unavailable) → 5 colour variants. Reasoning is surfaced as a tooltip
 * (native `title` attr) so we don't pull in a tooltip lib.
 */
const STYLES: Record<AssessmentLabel | 'unknown', string> = {
  建议对冲: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  对冲有价值: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
  谨慎对冲: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  不建议对冲: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
  unknown: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
};

const I18N_KEY: Record<AssessmentLabel | 'unknown', string> = {
  建议对冲: 'hedge.result.assessmentBadge.buildHedge',
  对冲有价值: 'hedge.result.assessmentBadge.valuable',
  谨慎对冲: 'hedge.result.assessmentBadge.cautious',
  不建议对冲: 'hedge.result.assessmentBadge.notRecommended',
  unknown: 'hedge.result.assessmentBadge.unknown',
};

export function ModelInsightBadge({ assessment }: Props) {
  const t = useT();
  const key = assessment ?? 'unknown';

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold',
        STYLES[key],
      )}
    >
      <Info size={12} aria-hidden />
      {t(I18N_KEY[key])}
    </span>
  );
}
