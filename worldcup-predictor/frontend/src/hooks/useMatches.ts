/**
 * SWR-backed match data hooks.
 *
 * Each hook is a thin wrapper over `useSWR(url, swrFetcher)` so caching +
 * revalidation behave consistently. Pages typically call one of these and
 * pass the returned `data` array straight to a list component.
 */
'use client';

import useSWR from 'swr';

import { swrFetcher } from '@/lib/api';
import type { MatchSummary } from '@/types';

interface UseMatchesResult<T> {
  data: T | undefined;
  isLoading: boolean;
  error: unknown;
  refresh: () => Promise<T | undefined>;
}

/** Today's matches list (or any specific date via the optional param). */
export function useMatchesToday(date?: string): UseMatchesResult<MatchSummary[]> {
  const url = date ? `/api/v1/matches/today?date=${date}` : '/api/v1/matches/today';
  const { data, error, isLoading, mutate } = useSWR<MatchSummary[]>(url, swrFetcher, {
    revalidateOnFocus: false,
    revalidateOnReconnect: true,
    dedupingInterval: 30_000,
  });
  return { data, isLoading, error, refresh: mutate };
}

/** Single match detail. */
export function useMatchDetail(matchId: number | string): UseMatchesResult<MatchSummary> {
  const { data, error, isLoading, mutate } = useSWR<MatchSummary>(
    `/api/v1/matches/${matchId}`,
    swrFetcher,
    { revalidateOnFocus: false, dedupingInterval: 60_000 },
  );
  return { data, isLoading, error, refresh: mutate };
}
