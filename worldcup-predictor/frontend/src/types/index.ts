/**
 * TypeScript types for the WCP frontend.
 *
 * Mirrors the Java service's DTOs (`com.wcp.dto.response.*`) one-for-one — when
 * the backend contract changes the failing types here flag the breakage at
 * compile time. Any new field added on the Java side should land here in the
 * same PR.
 */

// --- Core enums ----------------------------------------------------------

export type MatchStatus = 'scheduled' | 'live' | 'finished' | 'postponed' | 'cancelled';
export type SubscriptionTier = 'free' | 'basic' | 'premium';
export type ConfidenceLevel = 'low' | 'medium' | 'high';
/** 0 = no signal, 3 = ⭐⭐⭐ strong value. */
export type SignalLevel = 0 | 1 | 2 | 3;

// --- Auth ---------------------------------------------------------------

export interface UserResponse {
  uuid: string;
  phone: string | null;
  email: string | null;
  nickname: string | null;
  avatarUrl: string | null;
  subscriptionTier: SubscriptionTier;
  subscriptionExpires: string | null; // ISO-8601
  locale: string;
  timezone: string;
  role: 'user' | 'admin';
}

export interface AuthResponse {
  accessToken: string;
  refreshToken: string;
  expiresInSeconds: number;
  user: UserResponse;
}

// --- Match summary (today + detail responses) ---------------------------

export interface TeamStatRow {
  label: string;
  home: string;
  away: string;
}

export interface H2HSummary {
  totalMatches: number;
  homeWins: number;
  draws: number;
  awayWins: number;
  avgGoals: number;
  lastMatchDate?: string | null;
}

export interface MatchSummary {
  matchId: number;
  matchDate: string; // ISO-8601
  homeTeam: string;
  awayTeam: string;
  competition: string | null;
  status: MatchStatus;

  probHomeWin: number | null;
  probDraw: number | null;
  probAwayWin: number | null;
  confidenceScore: number | null;
  confidenceLevel: ConfidenceLevel | null;

  /** True when the user can see at least one value signal. */
  hasValueSignal: boolean | null;
  topSignalLevel: SignalLevel | null;

  /** Paid content — null for free users. */
  oddsAnalysis: Record<string, unknown> | null;
  scoreMatrix: number[][] | null;
  overUnderProbs: Record<string, { over: number; under: number }> | null;

  /** Server hint for the paywall. */
  locked: boolean;

  /** Detail-page only — null on list views. */
  teamStats?: TeamStatRow[] | null;
  h2h?: H2HSummary | null;
  venue?: string | null;
  round?: string | null;
  homeScore?: number | null;
  awayScore?: number | null;

  /** Detail-page only when authenticated. Null for anonymous callers / list views. */
  favorited?: boolean | null;
}

// --- Subscription / payments --------------------------------------------

export interface SubscriptionPlan {
  tier: 'basic' | 'premium';
  planType: 'monthly' | 'worldcup_pass';
  /** Display price (USD cents). The user-facing default everywhere. */
  priceUsd: number;
  /** Charge price (CNY fen). Surfaced when the user picks Alipay / WeChat. */
  priceCny: number;
  durationDays: number;
  displayName: string;
}

export interface PaymentInitResponse {
  orderNo: string;
  paymentChannel: 'alipay' | 'wechat_pay';
  /** USD cents — what the receipt + history shows. */
  amountUsd: number;
  /** CNY fen — what Alipay / WeChat actually charges. */
  amountCny: number;
  paymentParams: Record<string, unknown>;
}

export interface CurrentSubscriptionResponse {
  active: boolean;
  tier: SubscriptionTier;
  planType?: 'monthly' | 'worldcup_pass';
  expiresAt?: string;
  autoRenew?: boolean;
}

// --- Track record -------------------------------------------------------

export interface TrackRecordOverview {
  statType: 'overall' | '1x2' | 'score' | 'ou25' | 'btts' | 'positive_ev';
  period: 'all_time' | 'last_30d' | 'last_7d' | 'worldcup';
  totalPredictions: number;
  hits: number;
  hitRate: number; // 0..1
  totalPnlUnits: number;
  roi: number; // 0..1 (signed)
  currentStreak: number;
  bestStreak: number;
  updatedAt: string | null;
}

export interface RoiTimeseriesPoint {
  date: string; // YYYY-MM-DD
  cumulativePnl: number;
  cumulativeRoi: number; // 0..1 signed
  settledCount: number;
}

export interface RoiTimeseries {
  period: 'all_time' | 'last_30d' | 'last_7d' | 'worldcup';
  points: RoiTimeseriesPoint[];
}

// --- Share links --------------------------------------------------------

export interface ShareLinkResponse {
  shortCode: string;
  shareUrl: string;
  shareLinkId: number;
  clickCount: number;
  registerCount: number;
  subscribeCount: number;
}

// --- Generic API envelope used by the Java service for errors ----------

export interface ApiError {
  code: number;
  error: string;
  message: string;
  details?: unknown;
}
