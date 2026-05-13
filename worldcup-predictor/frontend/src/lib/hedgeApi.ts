/**
 * M9 hedge advisory — API client.
 *
 * All endpoints live on the Java business service under `/api/v1/hedge/`;
 * the Java layer forwards single-bet / parlay create requests to ml-api
 * via `MlApiClient.hedgeCalculate` / `hedgeParlay` and then re-reads the
 * persisted scenario before returning to the browser.
 *
 * Authentication: the shared axios instance attaches the JWT bearer
 * automatically. No additional headers needed here.
 *
 * Field-name convention: every payload uses **camelCase** to match Spring's
 * default Jackson serialiser. Don't mix in snake_case keys — Spring will
 * silently drop them.
 */
import type {
  CreateScenarioRequest,
  HedgeHistoryResponse,
  HedgeStatsResponse,
  RecalcResponse,
  ScenarioResponse,
} from '@/types/hedge';

import { apiGet, apiPost } from './api';

/** POST /api/v1/hedge/scenarios — create a hedge scenario (single or parlay). */
export async function createScenario(
  body: CreateScenarioRequest,
): Promise<ScenarioResponse> {
  return apiPost<ScenarioResponse, CreateScenarioRequest>(
    '/api/v1/hedge/scenarios',
    body,
  );
}

/** GET /api/v1/hedge/scenarios — paged history (Spring Data Page wire shape). */
export async function listScenarios(
  page = 0,
  size = 20,
): Promise<{ content: ScenarioResponse[]; totalElements: number }> {
  return apiGet(`/api/v1/hedge/scenarios?page=${page}&size=${size}`);
}

/** GET /api/v1/hedge/scenarios/{id} — single scenario with calculations + legs. */
export async function getScenario(id: number): Promise<ScenarioResponse> {
  return apiGet<ScenarioResponse>(`/api/v1/hedge/scenarios/${id}`);
}

/** POST /api/v1/hedge/scenarios/{id}/recalc — re-run with latest odds. */
export async function recalcScenario(id: number): Promise<RecalcResponse> {
  return apiPost<RecalcResponse>(`/api/v1/hedge/scenarios/${id}/recalc`);
}

/** GET /api/v1/hedge/stats — aggregate ROI + win-rate. */
export async function fetchHedgeStats(): Promise<HedgeStatsResponse> {
  return apiGet<HedgeStatsResponse>('/api/v1/hedge/stats');
}

/** GET /api/v1/hedge/results — settled-scenario history. */
export async function fetchHedgeResults(): Promise<HedgeHistoryResponse> {
  return apiGet<HedgeHistoryResponse>('/api/v1/hedge/results');
}
