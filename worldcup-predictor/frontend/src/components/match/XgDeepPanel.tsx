'use client';

import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { useT } from '@/i18n/I18nProvider';
import { cn, formatPercent } from '@/lib/utils';
import type { MatchSummary } from '@/types';

interface Props {
  match: MatchSummary;
}

/**
 * Premium-only deep-stats panel.
 *
 * Replaces the originally-promised "xG / injuries" feature with what we
 * actually have data for: expected total goals (derived from the
 * over/under distribution), per-team attacking + defensive form (last-5
 * game stats from team_stats), goal-count distribution, and BTTS.
 *
 * Free / basic users get the panel blurred via PaywallOverlay; the
 * component itself doesn't gate — that's the wrapper's job. We only need
 * to handle the empty-data case (preseason, no team_stats yet).
 */
export function XgDeepPanel({ match }: Props) {
  const t = useT();
  const teamStats = match.teamStats ?? [];
  const oUProbs = match.overUnderProbs ?? null;

  // Pull the canonical "last 5" rows, falling back to label_key matches
  // because Java forwards both labelKey + label_key in different shapes.
  const find = (key: string) => teamStats.find((r) => keyOf(r) === key);
  const goalsForRow = find('match.form.last5GoalsFor');
  const goalsAgainstRow = find('match.form.last5GoalsAgainst');
  const winRateRow = find('match.form.last5WinRate');

  const expectedTotal = computeExpectedTotal(oUProbs, teamStats);
  const distribution = computeGoalDistribution(oUProbs);

  const empty = teamStats.length === 0 && !oUProbs;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="text-sm font-semibold text-slate-100">{t('deepStats.title')}</h3>
          <span className="text-xs text-slate-400">{t('deepStats.subtitle')}</span>
        </div>
      </CardHeader>
      <CardBody className="space-y-5">
        {empty ? (
          <div className="py-6 text-center text-xs text-slate-500">{t('deepStats.empty')}</div>
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-2">
              <Tile
                label={t('deepStats.expectedTotalGoals')}
                value={expectedTotal != null ? expectedTotal.toFixed(2) : '—'}
                hint={t('deepStats.scoreDistributionSub')}
                accent="cyan"
              />
              <Tile
                label={t('deepStats.scoringEfficiency')}
                value={efficiencyText(goalsForRow, expectedTotal)}
                hint={t('deepStats.scoringEfficiencyHint')}
                accent="emerald"
              />
            </div>

            {distribution.length > 0 ? (
              <Section
                title={t('deepStats.scoreDistribution')}
                hint={t('deepStats.scoreDistributionSub')}
              >
                <DistributionBar segments={distribution} />
              </Section>
            ) : null}

            {(goalsForRow || goalsAgainstRow || winRateRow) && (
              <Section title={t('deepStats.form5')}>
                <div className="space-y-2.5">
                  {goalsForRow ? (
                    <FormRow
                      label={t('deepStats.attackingPower')}
                      hint={t('deepStats.attackingPowerSub')}
                      home={goalsForRow.home}
                      away={goalsForRow.away}
                      homeTeam={match.homeTeam}
                      awayTeam={match.awayTeam}
                      barMax={3.5}
                    />
                  ) : null}
                  {goalsAgainstRow ? (
                    <FormRow
                      label={t('deepStats.defensiveSolidity')}
                      hint={t('deepStats.defensiveSolidiveSub')}
                      home={goalsAgainstRow.home}
                      away={goalsAgainstRow.away}
                      homeTeam={match.homeTeam}
                      awayTeam={match.awayTeam}
                      barMax={3.5}
                      lowerIsBetter
                    />
                  ) : null}
                  {winRateRow ? (
                    <FormRow
                      label={t('deepStats.winRate')}
                      home={winRateRow.home}
                      away={winRateRow.away}
                      homeTeam={match.homeTeam}
                      awayTeam={match.awayTeam}
                      isPercent
                    />
                  ) : null}
                </div>
              </Section>
            )}
          </>
        )}
      </CardBody>
    </Card>
  );
}

/* ------------------------------------------------------------------ */
/* Layout helpers                                                     */
/* ------------------------------------------------------------------ */

function Tile({
  label,
  value,
  hint,
  accent,
}: {
  label: string;
  value: string;
  hint: string;
  accent: 'cyan' | 'emerald';
}) {
  return (
    <div className="rounded-xl border border-slate-800/70 bg-slate-900/40 p-4">
      <div className="text-[11px] uppercase tracking-wider text-slate-400">{label}</div>
      <div
        className={cn(
          'mt-1 text-3xl font-bold tabular-nums',
          accent === 'cyan' ? 'text-cyan-300' : 'text-emerald-300',
        )}
      >
        {value}
      </div>
      <div className="mt-1 text-[11px] text-slate-500">{hint}</div>
    </div>
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

interface DistSeg {
  label: string;
  prob: number;
}

function DistributionBar({ segments }: { segments: DistSeg[] }) {
  // Distribution colours go from cool → warm as goal totals climb.
  const palette = [
    'bg-slate-600/80',
    'bg-emerald-500/80',
    'bg-cyan-500/80',
    'bg-amber-500/80',
    'bg-rose-500/80',
  ];
  return (
    <div className="space-y-2">
      <div className="flex h-7 overflow-hidden rounded-md bg-slate-800/60">
        {segments.map((seg, i) => {
          const pct = seg.prob * 100;
          if (pct < 0.5) return null;
          return (
            <div
              key={seg.label}
              style={{ width: `${pct}%` }}
              className={cn(
                'flex items-center justify-center text-[11px] font-semibold tabular-nums text-white',
                palette[i % palette.length],
              )}
              title={`${seg.label} · ${formatPercent(seg.prob)}`}
            >
              {pct >= 14 ? formatPercent(seg.prob) : null}
            </div>
          );
        })}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-slate-400">
        {segments.map((seg, i) => (
          <span key={seg.label} className="inline-flex items-center gap-1.5">
            <span className={cn('h-2 w-2 rounded-sm', palette[i % palette.length])} />
            {seg.label}
          </span>
        ))}
      </div>
    </div>
  );
}

interface FormRowProps {
  label: string;
  hint?: string;
  home: number | string;
  away: number | string;
  homeTeam: string;
  awayTeam: string;
  isPercent?: boolean;
  barMax?: number;
  lowerIsBetter?: boolean;
}

function FormRow({
  label,
  hint,
  home,
  away,
  homeTeam,
  awayTeam,
  isPercent = false,
  barMax,
  lowerIsBetter = false,
}: FormRowProps) {
  const homeNum = parseStat(home);
  const awayNum = parseStat(away);
  const max = barMax ?? Math.max(homeNum, awayNum, isPercent ? 1 : 1);
  const homeWidth = max > 0 ? Math.min(100, (homeNum / max) * 100) : 0;
  const awayWidth = max > 0 ? Math.min(100, (awayNum / max) * 100) : 0;
  const homeLeads = lowerIsBetter ? homeNum < awayNum : homeNum > awayNum;
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between text-[11px] text-slate-400">
        <span>{label}</span>
        {hint ? <span className="text-slate-500">{hint}</span> : null}
      </div>
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 text-xs">
        <div className="flex items-center justify-end gap-2">
          <span className="truncate text-slate-300">{homeTeam}</span>
          <span
            className={cn(
              'font-semibold tabular-nums',
              homeLeads ? 'text-emerald-300' : 'text-slate-200',
            )}
          >
            {String(home)}
          </span>
          <div className="relative h-1.5 w-20 rounded-full bg-slate-800">
            <div
              style={{ width: `${homeWidth}%` }}
              className={cn(
                'absolute right-0 top-0 h-full rounded-full',
                homeLeads ? 'bg-emerald-400' : 'bg-slate-500',
              )}
            />
          </div>
        </div>
        <div className="text-[10px] text-slate-500">vs</div>
        <div className="flex items-center gap-2">
          <div className="relative h-1.5 w-20 rounded-full bg-slate-800">
            <div
              style={{ width: `${awayWidth}%` }}
              className={cn(
                'absolute left-0 top-0 h-full rounded-full',
                !homeLeads ? 'bg-emerald-400' : 'bg-slate-500',
              )}
            />
          </div>
          <span
            className={cn(
              'font-semibold tabular-nums',
              !homeLeads ? 'text-emerald-300' : 'text-slate-200',
            )}
          >
            {String(away)}
          </span>
          <span className="truncate text-slate-300">{awayTeam}</span>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Math                                                               */
/* ------------------------------------------------------------------ */

type StatRow = { label?: string; labelKey?: string | null; label_key?: string | null; home: number | string; away: number | string };

function keyOf(row: StatRow): string | null {
  return (row.labelKey ?? row.label_key ?? null) || null;
}

function parseStat(v: number | string): number {
  if (typeof v === 'number') return v;
  // "40%" → 0.4
  if (v.endsWith('%')) return Number(v.slice(0, -1)) / 100 || 0;
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

/**
 * Best-effort expected-total-goals estimate. Prefer the over/under 2.5
 * cumulative — given P(over 0.5), P(over 1.5), ... we can recover the
 * goal-count probability mass and take the expectation. Falls back to
 * summing the team_stats "last-5 goals scored" averages.
 */
function computeExpectedTotal(
  oUProbs: MatchSummary['overUnderProbs'],
  teamStats: StatRow[],
): number | null {
  if (oUProbs && typeof oUProbs === 'object') {
    const dist = goalProbabilityMass(oUProbs);
    if (dist) {
      let exp = 0;
      for (let n = 0; n < dist.length; n++) {
        // The last bucket is "n+ goals" — use n as a lower bound.
        exp += n * dist[n];
      }
      return exp;
    }
  }
  // Fallback: sum the home/away "goals for" averages from the form table.
  const gf = teamStats.find((r) => keyOf(r) === 'match.form.last5GoalsFor');
  if (gf) {
    return parseStat(gf.home) + parseStat(gf.away);
  }
  return null;
}

/**
 * Convert {1.5: {over,under}, 2.5: {over,under}, 3.5: {over,under}} into
 * a 5-bucket probability mass: P(0), P(1), P(2), P(3), P(4+). Each
 * bucket = P(over_n-0.5) - P(over_n+0.5).
 */
function goalProbabilityMass(
  ouProbs: NonNullable<MatchSummary['overUnderProbs']>,
): number[] | null {
  const overs: Record<number, number> = {};
  for (const [thresh, val] of Object.entries(ouProbs)) {
    const t = Number(thresh);
    if (!Number.isFinite(t) || !val || typeof (val as { over?: number }).over !== 'number') continue;
    overs[t] = (val as { over: number }).over;
  }
  // Need at least the .5, 1.5, 2.5, 3.5 thresholds — if any are missing,
  // bail and let the caller fall back to the form-table heuristic.
  if (overs[1.5] == null || overs[2.5] == null || overs[3.5] == null) return null;
  // Synthesise overs[0.5] when missing: P(>= 1 goal) ≥ P(>= 2) and is
  // bounded by 1; a reasonable proxy when ml-api drops it on smaller
  // distributions is `min(1, overs[1.5] + 0.15)`.
  const o05 = overs[0.5] ?? Math.min(1, overs[1.5] + 0.15);
  const p0 = Math.max(0, 1 - o05);
  const p1 = Math.max(0, o05 - overs[1.5]);
  const p2 = Math.max(0, overs[1.5] - overs[2.5]);
  const p3 = Math.max(0, overs[2.5] - overs[3.5]);
  const p4plus = Math.max(0, overs[3.5]);
  return [p0, p1, p2, p3, p4plus];
}

function efficiencyText(goalsForRow: StatRow | undefined, expectedTotal: number | null): string {
  if (!goalsForRow || expectedTotal == null || expectedTotal <= 0) return '—';
  // Both teams' "last-5 goals scored" combined vs the AI-derived
  // expected total. Above 1.0 = teams have been outperforming the
  // model's per-match expectation lately.
  const recent = parseStat(goalsForRow.home) + parseStat(goalsForRow.away);
  const ratio = recent / expectedTotal;
  return `${ratio.toFixed(2)}×`;
}

function computeGoalDistribution(
  ouProbs: MatchSummary['overUnderProbs'],
): DistSeg[] {
  if (!ouProbs) return [];
  const dist = goalProbabilityMass(ouProbs);
  if (!dist) return [];
  return [
    { label: '0 球', prob: dist[0] },
    { label: '1 球', prob: dist[1] },
    { label: '2 球', prob: dist[2] },
    { label: '3 球', prob: dist[3] },
    { label: '4+ 球', prob: dist[4] },
  ];
}
