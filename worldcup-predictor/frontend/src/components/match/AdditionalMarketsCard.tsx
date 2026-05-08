'use client';

import { useEffect, useState } from 'react';

import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { useT } from '@/i18n/I18nProvider';
import { cn, formatPercent } from '@/lib/utils';

interface OverUnderItem {
  threshold: number;
  over: number;
  under: number;
}

interface FirstToScore {
  home: number;
  no_goal: number;
  away: number;
}

interface AdditionalMarketsResponse {
  match_id: number;
  btts_yes: number;
  btts_no: number;
  expected_goals: number;
  expected_corners: number;
  expected_cards: number;
  corners: OverUnderItem[];
  cards: OverUnderItem[];
  first_to_score: FirstToScore;
}

interface Props {
  matchId: number;
}

/**
 * Renders the secondary betting markets (corners, yellow cards, both-teams-
 * score, first-to-score) that we derive client-side from the published
 * prediction's lambda values. The endpoint is public (no auth) so we hit
 * it through nginx straight from the browser — keeps SSR simple.
 */
export function AdditionalMarketsCard({ matchId }: Props) {
  const t = useT();
  const [data, setData] = useState<AdditionalMarketsResponse | null>(null);
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`/api/v1/markets/${matchId}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((body: AdditionalMarketsResponse) => {
        if (!cancelled) setData(body);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [matchId]);

  if (loading) {
    return (
      <Card>
        <CardHeader>
          <h3 className="text-sm font-semibold text-slate-100">{t('markets.title')}</h3>
        </CardHeader>
        <CardBody>
          <div className="animate-pulse text-xs text-slate-500">{t('markets.loading')}</div>
        </CardBody>
      </Card>
    );
  }

  if (error || !data) {
    return null;
  }

  return (
    <Card>
      <CardHeader>
        <h3 className="text-sm font-semibold text-slate-100">{t('markets.title')}</h3>
        <span className="text-xs text-slate-400">{t('markets.subtitle')}</span>
      </CardHeader>
      <CardBody className="space-y-5">
        <BttsRow yes={data.btts_yes} no={data.btts_no} />
        <FirstToScoreRow value={data.first_to_score} />
        <OverUnderBlock
          title={t('markets.corners')}
          expectedLabel={t('markets.expectedCorners')}
          expected={data.expected_corners}
          rows={data.corners}
        />
        <OverUnderBlock
          title={t('markets.cards')}
          expectedLabel={t('markets.expectedCards')}
          expected={data.expected_cards}
          rows={data.cards}
        />
        <p className="border-t border-slate-800/70 pt-3 text-[11px] leading-relaxed text-slate-500">
          {t('markets.footnote')}
        </p>
      </CardBody>
    </Card>
  );
}

function BttsRow({ yes, no }: { yes: number; no: number }) {
  const t = useT();
  return (
    <Section title={t('markets.btts')}>
      <SplitBar
        segments={[
          { label: t('markets.btts_yes'), value: yes, tone: 'good' },
          { label: t('markets.btts_no'), value: no, tone: 'muted' },
        ]}
      />
    </Section>
  );
}

function FirstToScoreRow({ value }: { value: FirstToScore }) {
  const t = useT();
  return (
    <Section title={t('markets.firstToScore')} hint={t('markets.firstToScoreSub')}>
      <SplitBar
        segments={[
          { label: t('markets.ftsHome'), value: value.home, tone: 'good' },
          { label: t('markets.ftsNoGoal'), value: value.no_goal, tone: 'muted' },
          { label: t('markets.ftsAway'), value: value.away, tone: 'warn' },
        ]}
      />
    </Section>
  );
}

function OverUnderBlock({
  title,
  rows,
  expected,
  expectedLabel,
}: {
  title: string;
  rows: OverUnderItem[];
  expected: number;
  expectedLabel: string;
}) {
  const t = useT();
  return (
    <Section title={title} hint={`${expectedLabel} ${expected.toFixed(1)}`}>
      <div className="space-y-2">
        {rows.map((row) => (
          <div key={row.threshold} className="flex items-center gap-3">
            <div className="w-16 text-xs tabular-nums text-slate-400">
              {row.threshold.toFixed(1)}
            </div>
            <div className="flex-1">
              <SplitBar
                compact
                segments={[
                  { label: t('markets.over'), value: row.over, tone: 'good' },
                  { label: t('markets.under'), value: row.under, tone: 'muted' },
                ]}
              />
            </div>
          </div>
        ))}
      </div>
    </Section>
  );
}

function Section({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <div className="text-xs font-semibold uppercase tracking-wider text-slate-300">
          {title}
        </div>
        {hint ? <div className="text-[11px] text-slate-500">{hint}</div> : null}
      </div>
      {children}
    </div>
  );
}

interface Segment {
  label: string;
  value: number; // 0..1
  tone: 'good' | 'warn' | 'muted';
}

const TONE_BG: Record<Segment['tone'], string> = {
  good: 'bg-emerald-500/80 text-white',
  warn: 'bg-rose-500/80 text-white',
  muted: 'bg-amber-500/70 text-slate-900',
};

function SplitBar({ segments, compact = false }: { segments: Segment[]; compact?: boolean }) {
  const total = segments.reduce((sum, s) => sum + s.value, 0) || 1;
  return (
    <div
      className={cn(
        'flex w-full overflow-hidden rounded-md bg-slate-800/60',
        compact ? 'h-6 text-[11px]' : 'h-8 text-xs',
      )}
    >
      {segments.map((seg, i) => {
        const pct = (seg.value / total) * 100;
        if (pct < 0.5) return null;
        return (
          <div
            key={`${seg.label}-${i}`}
            style={{ width: `${pct}%` }}
            className={cn(
              'flex items-center justify-center font-semibold tabular-nums',
              TONE_BG[seg.tone],
            )}
            title={`${seg.label} ${formatPercent(seg.value)}`}
          >
            {pct >= 14 ? `${seg.label} ${formatPercent(seg.value)}` : formatPercent(seg.value)}
          </div>
        );
      })}
    </div>
  );
}
