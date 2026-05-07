import type { CompactMatch } from '@/components/match/CompactMatchCard';

/** Map ml-api's snake_case OR Java's camelCase compact match payload. */
export function toCompactMatch(raw: Record<string, unknown>): CompactMatch | null {
  const id = pickNumber(raw, 'matchId', 'match_id');
  if (id === null) return null;
  const dateRaw = pickString(raw, 'matchDate', 'match_date');
  if (!dateRaw) return null;
  return {
    matchId: id,
    matchDate: dateRaw,
    homeTeam: pickString(raw, 'homeTeam', 'home_team') ?? '?',
    awayTeam: pickString(raw, 'awayTeam', 'away_team') ?? '?',
    homeTeamLogo: pickString(raw, 'homeTeamLogo', 'home_team_logo'),
    awayTeamLogo: pickString(raw, 'awayTeamLogo', 'away_team_logo'),
    competition: pickString(raw, 'competition', 'competition'),
    status: pickString(raw, 'status', 'status') ?? 'scheduled',
    round: pickString(raw, 'round', 'round'),
    homeScore: pickNumber(raw, 'homeScore', 'home_score'),
    awayScore: pickNumber(raw, 'awayScore', 'away_score'),
    probHomeWin: pickNumber(raw, 'probHomeWin', 'prob_home_win'),
    probDraw: pickNumber(raw, 'probDraw', 'prob_draw'),
    probAwayWin: pickNumber(raw, 'probAwayWin', 'prob_away_win'),
    confidenceScore: pickNumber(raw, 'confidenceScore', 'confidence_score'),
  };
}

export function toCompactMatches(raw: unknown): CompactMatch[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((r): r is Record<string, unknown> => typeof r === 'object' && r !== null)
    .map(toCompactMatch)
    .filter((m): m is CompactMatch => m !== null);
}

function pickString(
  obj: Record<string, unknown>,
  camel: string,
  snake: string,
): string | null {
  const value = obj[camel] ?? obj[snake];
  return typeof value === 'string' ? value : null;
}

function pickNumber(
  obj: Record<string, unknown>,
  camel: string,
  snake: string,
): number | null {
  const value = obj[camel] ?? obj[snake];
  if (value === null || value === undefined) return null;
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}
