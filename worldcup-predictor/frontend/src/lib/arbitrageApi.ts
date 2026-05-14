import { api, apiGet, apiPost } from './api';
import type {
  ArbOpportunity,
  CreateWatchlistRequest,
  WatchlistEntry,
} from '@/types/arbitrage';

const BASE = '/api/v1/arbitrage';

export async function listOpportunities(
  marketType?: string,
  minProfitMargin?: number,
  limit: number = 50,
): Promise<ArbOpportunity[]> {
  const params = new URLSearchParams();
  params.set('limit', String(limit));
  if (marketType) params.set('marketType', marketType);
  if (minProfitMargin != null) params.set('minProfitMargin', String(minProfitMargin));
  return apiGet<ArbOpportunity[]>(`${BASE}/opportunities?${params}`);
}

export async function getOpportunity(id: number): Promise<ArbOpportunity> {
  return apiGet<ArbOpportunity>(`${BASE}/opportunities/${id}`);
}

export async function listWatchlist(): Promise<WatchlistEntry[]> {
  return apiGet<WatchlistEntry[]>(`${BASE}/watchlist`);
}

export async function createWatchlist(body: CreateWatchlistRequest): Promise<WatchlistEntry> {
  return apiPost<WatchlistEntry, CreateWatchlistRequest>(`${BASE}/watchlist`, body);
}

export async function deleteWatchlist(id: number): Promise<void> {
  await api.delete(`${BASE}/watchlist/${id}`);
}

/** Tolerates both snake_case (Python passthrough) and camelCase (Java) keys. */
export function readOpportunityField<T>(
  opp: ArbOpportunity,
  snake: keyof ArbOpportunity,
  camel: keyof ArbOpportunity,
): T | undefined {
  return (opp[snake] ?? opp[camel]) as T | undefined;
}
