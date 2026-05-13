/** M10 arbitrage types mirroring the Java DTOs. */

export type ArbMarketType = '1x2' | 'over_under' | 'asian_handicap' | 'btts';
export type ArbStatus = 'active' | 'expired' | 'stale';

export interface ArbBestQuote {
  odds: number | string;
  bookmaker: string;
  captured_at?: string | null;
  capturedAt?: string | null;
}

export interface ArbOpportunity {
  id: number;
  match_id?: number;
  matchId?: number;
  market_type?: ArbMarketType | string;
  marketType?: ArbMarketType | string;
  detected_at?: string;
  detectedAt?: string;
  arb_total?: number | string;
  arbTotal?: number | string;
  profit_margin?: number | string;
  profitMargin?: number | string;
  best_odds?: Record<string, ArbBestQuote>;
  bestOdds?: Record<string, ArbBestQuote>;
  stake_distribution?: Record<string, number | string>;
  stakeDistribution?: Record<string, number | string>;
  status: ArbStatus;
  expired_at?: string | null;
  expiredAt?: string | null;
}

export interface WatchlistEntry {
  id: number;
  userId: number;
  competitionId: number | null;
  marketTypes: string[] | null;
  minProfitMargin: number;
  notifyEnabled: boolean;
  createdAt: string;
}

export interface CreateWatchlistRequest {
  competitionId?: number | null;
  marketTypes?: string[] | null;
  minProfitMargin?: number;
  notifyEnabled?: boolean;
}
