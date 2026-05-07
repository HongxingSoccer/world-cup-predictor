import type { Metadata } from 'next';
import { notFound } from 'next/navigation';

import type { CompactMatch } from '@/components/match/CompactMatchCard';
import { FavoriteButton } from '@/components/match/FavoriteButton';
import { H2HPanel } from '@/components/match/H2HPanel';
import { MatchHeader } from '@/components/match/MatchHeader';
import { OddsCompareTable, type OddsRow } from '@/components/match/OddsCompareTable';
import { PredictionPanel } from '@/components/match/PredictionPanel';
import { RelatedMatches } from '@/components/match/RelatedMatches';
import { ScoreMatrix } from '@/components/match/ScoreMatrix';
import { TeamStatsPanel } from '@/components/match/TeamStatsPanel';
import { ShareButton } from '@/components/share/ShareButton';
import { PaywallOverlay } from '@/components/subscription/PaywallOverlay';
import { toCompactMatches } from '@/lib/match-mappers';
import type { MatchSummary, SignalLevel } from '@/types';

interface MatchPageProps {
  params: { id: string };
}

function ssrBaseUrl(): string {
  // Server-side fetches inside docker can't reach the published nginx port via
  // localhost — they must hit the java-api service over the docker network.
  // SERVER_API_URL is set in docker-compose for that path; falls back to the
  // browser-visible URL outside docker.
  return (
    process.env.SERVER_API_URL ??
    process.env.NEXT_PUBLIC_API_URL ??
    'http://localhost:8080'
  );
}

async function fetchMatch(id: string): Promise<MatchSummary | null> {
  try {
    const response = await fetch(`${ssrBaseUrl()}/api/v1/matches/${id}`, {
      next: { revalidate: 60 },
    });
    if (!response.ok) return null;
    return (await response.json()) as MatchSummary;
  } catch {
    return null;
  }
}

async function fetchRelated(id: string): Promise<CompactMatch[]> {
  try {
    const response = await fetch(
      `${ssrBaseUrl()}/api/v1/matches/${id}/related?limit=6`,
      { next: { revalidate: 300 } },
    );
    if (!response.ok) return [];
    return toCompactMatches(await response.json());
  } catch {
    return [];
  }
}

export async function generateMetadata({ params }: MatchPageProps): Promise<Metadata> {
  const match = await fetchMatch(params.id);
  if (!match) {
    return { title: '比赛未找到' };
  }
  const homeProb =
    match.probHomeWin != null ? `${(match.probHomeWin * 100).toFixed(0)}%胜率` : 'AI 预测';
  return {
    title: `${match.homeTeam} vs ${match.awayTeam} 预测`,
    description: `${match.competition ?? 'WCP'} · ${match.homeTeam} vs ${match.awayTeam} — ${homeProb}, 比分概率, 价值信号。`,
    openGraph: {
      title: `${match.homeTeam} vs ${match.awayTeam} | AI模型: ${homeProb}`,
      description: `比分概率矩阵 · 赔率 EV 分析 · 价值信号 — ${match.competition ?? 'WCP'}`,
    },
  };
}

export default async function MatchDetailPage({ params }: MatchPageProps) {
  const [match, related] = await Promise.all([
    fetchMatch(params.id),
    fetchRelated(params.id),
  ]);
  if (!match) {
    notFound();
  }

  const teamStatsRows = match.teamStats ?? [];
  const h2hSummary = toH2hSummary(match.h2h);
  const oddsRows = toOddsRows(match.oddsAnalysis);

  const shareUrl = `/match/${match.matchId}`;

  return (
    <div className="space-y-4">
      <MatchHeader match={match} />

      <div className="grid gap-4 md:grid-cols-2">
        <PredictionPanel match={match} />

        <PaywallOverlay feature="score_matrix" featureLabel="比分概率矩阵">
          <ScoreMatrix matrix={match.scoreMatrix} />
        </PaywallOverlay>
      </div>

      <PaywallOverlay feature="odds_analysis" featureLabel="赔率价值分析">
        <OddsCompareTable rows={oddsRows} />
      </PaywallOverlay>

      <div className="grid gap-4 md:grid-cols-2">
        <TeamStatsPanel
          homeTeam={match.homeTeam}
          awayTeam={match.awayTeam}
          rows={teamStatsRows}
        />
        <H2HPanel
          homeTeam={match.homeTeam}
          awayTeam={match.awayTeam}
          summary={h2hSummary}
        />
      </div>

      <div className="flex items-center justify-between gap-3">
        <FavoriteButton
          matchId={match.matchId}
          initialFavorited={match.favorited}
        />
        <ShareButton
          targetType="match"
          targetId={match.matchId}
          targetUrl={shareUrl}
        />
      </div>

      <RelatedMatches matches={related} />
    </div>
  );
}

/** Normalize the h2h object — Java forwards ml-api's payload as a typeless
 * Map<String,Object>, so the snake_case keys flow through unchanged. */
function toH2hSummary(raw: MatchSummary['h2h'] | undefined): {
  totalMatches: number;
  homeWins: number;
  draws: number;
  awayWins: number;
  avgGoals: number;
  lastMatchDate?: string | null;
} {
  if (!raw || typeof raw !== 'object') {
    return { totalMatches: 0, homeWins: 0, draws: 0, awayWins: 0, avgGoals: 0 };
  }
  const r = raw as unknown as Record<string, unknown>;
  return {
    totalMatches: Number(r.totalMatches ?? r.total_matches ?? 0),
    homeWins: Number(r.homeWins ?? r.home_wins ?? 0),
    draws: Number(r.draws ?? 0),
    awayWins: Number(r.awayWins ?? r.away_wins ?? 0),
    avgGoals: Number(r.avgGoals ?? r.avg_goals ?? 0),
    lastMatchDate:
      (r.lastMatchDate as string | null | undefined) ??
      (r.last_match_date as string | null | undefined) ??
      null,
  };
}

/** Coerce ml-api's snake_case odds_analysis array into the camelCase OddsRow shape. */
function toOddsRows(raw: MatchSummary['oddsAnalysis']): OddsRow[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((r): r is Record<string, unknown> => typeof r === 'object' && r !== null)
    .map((r) => ({
      marketType: String(r.marketType ?? r.market_type ?? ''),
      marketValue:
        typeof (r.marketValue ?? r.market_value) === 'string'
          ? ((r.marketValue ?? r.market_value) as string)
          : null,
      outcome: String(r.outcome ?? ''),
      modelProb: Number(r.modelProb ?? r.model_prob ?? 0),
      bestOdds: Number(r.bestOdds ?? r.best_odds ?? 0),
      bestBookmaker: String(r.bestBookmaker ?? r.best_bookmaker ?? ''),
      impliedProb: Number(r.impliedProb ?? r.implied_prob ?? 0),
      ev: Number(r.ev ?? 0),
      edge: Number(r.edge ?? 0),
      signalLevel: ((Number(r.signalLevel ?? r.signal_level ?? 0) | 0) as SignalLevel),
    }));
}
