/**
 * Mirrors `com.wcp.positions.dto.PositionResponse` and
 * `com.wcp.notifications.dto.NotificationResponse` from the Java side.
 *
 * Stake / odds / settlementPnl come over the wire as JSON numbers (Jackson
 * serialises BigDecimal as a number by default in this service) so they're
 * typed as `number` here. The Java DTO is the canonical source of truth.
 */

export type PositionStatus = 'active' | 'hedged' | 'settled' | 'cancelled';
export type PositionMarket = '1x2' | 'over_under' | 'asian_handicap' | 'btts';
export type PositionOutcome =
  | 'home'
  | 'draw'
  | 'away'
  | 'over'
  | 'under'
  | 'yes'
  | 'no';

export interface PositionResponse {
  id: number;
  userId: number;
  matchId: number;
  platform: string | null;
  market: PositionMarket;
  outcome: string;
  stake: number;
  odds: number;
  placedAt: string; // ISO-8601
  status: PositionStatus;
  notes: string | null;
  createdAt: string;
  updatedAt: string;
  lastAlertAt: string | null;
  settlementPnl: number | null;
}

export interface CreatePositionRequest {
  matchId: number;
  platform?: string | null;
  market: PositionMarket;
  outcome: string;
  stake: number;
  odds: number;
  placedAt?: string | null;
  notes?: string | null;
}

export interface UpdateStatusRequest {
  status: PositionStatus;
}

// --- Notification centre -------------------------------------------------

export type NotificationKind =
  | 'hedge_window'
  | 'position_settled'
  | 'high_ev'
  | 'match_start'
  | 'red_hit'
  | 'ai_report'
  | 'arbitrage';

export interface NotificationResponse {
  id: number;
  kind: NotificationKind | string;
  title: string;
  body: string;
  positionId: number | null;
  matchId: number | null;
  targetUrl: string | null;
  payload: Record<string, unknown> | null;
  createdAt: string;
  readAt: string | null;
}

export interface NotificationListResponse {
  items: NotificationResponse[];
  unreadCount: number;
}
