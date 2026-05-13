'use client';

import { cn } from '@/lib/utils';
import { useT } from '@/i18n/I18nProvider';
import type { HedgeMode } from '@/types/hedge';
import { modeFromRatio } from '@/types/hedge';

interface Props {
  /** 0–100 (percent), not 0–1. Component handles the conversion. */
  value: number;
  onChange: (value: number) => void;
  disabled?: boolean;
}

/**
 * Tri-coloured slider that doubles as the hedge_mode picker.
 *
 * - 0-30  → risk     (green)
 * - 30-70 → partial  (blue)
 * - 70-100 → full    (gray)
 *
 * `<input type="range">` + a Tailwind gradient track. The thumb is a
 * native circle styled via the pseudo-elements `::-webkit-slider-thumb`
 * and `::-moz-range-thumb` in a tiny inline `<style>` block, which
 * avoids pulling in any non-stdlib UI dependency.
 */
export function HedgeModeSlider({ value, onChange, disabled }: Props) {
  const t = useT();
  const mode: HedgeMode = modeFromRatio(value / 100);
  const modeLabel = t(`hedge.modes.${mode}`);

  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between">
        <label
          htmlFor="hedge-ratio-slider"
          className="text-sm font-medium text-slate-200"
        >
          {t('hedge.slider.label')}
        </label>
        <span className="text-sm tabular-nums text-slate-300">
          {value.toString().padStart(2, ' ')}% &middot; {modeLabel}
        </span>
      </div>

      <input
        id="hedge-ratio-slider"
        type="range"
        min={0}
        max={100}
        step={5}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        disabled={disabled}
        aria-label={t('hedge.slider.label')}
        className={cn(
          'wcp-hedge-slider h-2 w-full appearance-none rounded-full',
          // Tri-colour gradient. Tailwind doesn't have arbitrary linear-
          // gradient classes inline, so we keep it as a `style` prop.
          disabled && 'cursor-not-allowed opacity-60',
        )}
        style={{
          background:
            'linear-gradient(to right, ' +
            '#22c55e 0%, #22c55e 30%, ' +
            '#3b82f6 30%, #3b82f6 70%, ' +
            '#94a3b8 70%, #94a3b8 100%)',
        }}
      />

      <div className="grid grid-cols-3 gap-2 text-xs text-slate-400">
        <span className="text-emerald-400">{t('hedge.slider.regions.risk')}</span>
        <span className="text-center text-sky-400">
          {t('hedge.slider.regions.partial')}
        </span>
        <span className="text-right text-slate-300">
          {t('hedge.slider.regions.full')}
        </span>
      </div>

      {/* Native slider thumb styling — small + self-contained so we don't
          touch globals.css for a component-local concern. */}
      <style jsx>{`
        .wcp-hedge-slider::-webkit-slider-thumb {
          -webkit-appearance: none;
          appearance: none;
          width: 18px;
          height: 18px;
          border-radius: 9999px;
          background: #f1f5f9;
          border: 2px solid #0f172a;
          cursor: pointer;
          box-shadow: 0 2px 6px rgba(0, 0, 0, 0.4);
        }
        .wcp-hedge-slider::-moz-range-thumb {
          width: 18px;
          height: 18px;
          border-radius: 9999px;
          background: #f1f5f9;
          border: 2px solid #0f172a;
          cursor: pointer;
        }
      `}</style>
    </div>
  );
}
