/**
 * M9 hedging types — frontend mirrors of the Java DTOs in
 * `com.wcp.hedge.dto`. Field names are camelCase to match Spring's
 * default Jackson serialisation.
 *
 * Decimal-typed columns on the server (NUMERIC(12,2) for money,
 * NUMERIC(8,3) for odds) come over the wire as JSON numbers. Some
 * have enough precision to overflow JS Number for adjacent fields
 * (BigDecimal can carry > 2^53), but for the hedge surface (money
 * < ¥10M, odds < 1000) the JS Number range is safe. If we ever
 * exceed that, switch to string transport on the Spring side.
 */

// ---------------------------------------------------------------------------
// Discrete enums — mirror Python `Literal[...]` aliases.
// ---------------------------------------------------------------------------

export type HedgeMode = 'full' | 'partial' | 'risk';
export type OutcomeType = 'home' | 'draw' | 'away' | 'over' | 'under';
export type MarketType = '1x2' | 'over_under' | 'asian_handicap' | 'btts';

/** Strict 4-string set; null when the model service couldn't supply probs. */
export type AssessmentLabel =
  | '建议对冲'
  | '对冲有价值'
  | '谨慎对冲'
  | '不建议对冲';

export type ScenarioType = 'single' | 'parlay' | 'live';

// ---------------------------------------------------------------------------
// POST /api/v1/hedge/scenarios — create request
// ---------------------------------------------------------------------------

/** Request body sent to the Java controller; legs is required for parlay. */
export interface CreateScenarioRequest {
  scenarioType: 'single' | 'parlay';
  matchId?: number; // omitted for parlay
  originalStake: number;
  originalOdds?: number; // required for single
  originalOutcome?: OutcomeType; // required for single
  originalMarket?: MarketType; // required for single
  hedgeMode: HedgeMode;
  hedgeRatio?: number | null;
  legs?: ParlayLegInput[]; // required for parlay
}

export interface ParlayLegInput {
  matchId: number;
  outcome: string;
  odds: number;
  isSettled: boolean;
  isWon?: boolean | null;
}

// ---------------------------------------------------------------------------
// Server responses
// ---------------------------------------------------------------------------

export interface HedgeCalculationDto {
  id: number;
  hedgeOutcome: string;
  hedgeOdds: number;
  hedgeBookmaker: string;
  hedgeStake: number;
  profitIfOriginalWins: number;
  profitIfHedgeWins: number;
  maxLoss: number;
  guaranteedProfit: number | null;
  evOfHedge: number | null;
  modelProbHedge: number | null;
  modelAssessment: AssessmentLabel | null;
}

export interface ParlayLegDto {
  legOrder: number;
  matchId: number;
  outcome: string;
  odds: number;
  isSettled: boolean;
  isWon: boolean | null;
}

export interface ScenarioResponse {
  scenarioId: number;
  scenarioType: ScenarioType;
  matchId: number | null;
  originalStake: number;
  originalOdds: number;
  originalOutcome: string;
  originalMarket: string;
  hedgeMode: HedgeMode;
  hedgeRatio: number;
  status: 'active' | 'settled' | 'cancelled';
  createdAt: string;
  calculations: HedgeCalculationDto[];
  legs: ParlayLegDto[];
  disclaimer: string;
}

export interface RecalcResponse {
  scenarioId: number;
  oldCalculationCount: number;
  newCalculationCount: number;
  calculations: HedgeCalculationDto[];
  disclaimer: string;
}

export interface HedgeStatsResponse {
  totalSettled: number;
  winningScenarios: number;
  totalPnl: number;
  totalWouldHavePnl: number;
  totalHedgeValueAdded: number;
  winRatePct: number;
  roiPct: number;
}

export interface HedgeHistoryItem {
  scenarioId: number;
  scenarioType: ScenarioType;
  matchId: number | null;
  actualOutcome: string;
  originalPnl: number;
  hedgePnl: number;
  totalPnl: number;
  wouldHavePnl: number;
  hedgeValueAdded: number;
  settledAt: string;
}

export interface HedgeHistoryResponse {
  items: HedgeHistoryItem[];
}

// ---------------------------------------------------------------------------
// UI-derived helpers
// ---------------------------------------------------------------------------

/** Default hedge_ratio inferred when the user picks a mode but no slider value. */
export const MODE_DEFAULT_RATIO: Record<HedgeMode, number> = {
  full: 1.0,
  partial: 0.6,
  risk: 0.3,
};

/** Inverse mapping for the slider — derive the mode label from a ratio. */
export function modeFromRatio(ratio: number): HedgeMode {
  if (ratio < 0.3) return 'risk';
  if (ratio < 0.7) return 'partial';
  return 'full';
}
