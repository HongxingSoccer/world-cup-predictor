/**
 * Shared utilities used across components: class-name helpers, formatters,
 * tier-checks. Anything sufficiently generic to be reused twice lives here.
 */
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

import type { SignalLevel, SubscriptionTier } from '@/types';

/** Tailwind-aware classname merger. Use `cn(...)` everywhere. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

// --- Formatting ----------------------------------------------------------

const PERCENT_FMT = new Intl.NumberFormat('zh-CN', {
  style: 'percent',
  minimumFractionDigits: 0,
  maximumFractionDigits: 1,
});

export function formatPercent(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  return PERCENT_FMT.format(value);
}

const SIGNED_PERCENT_FMT = new Intl.NumberFormat('zh-CN', {
  style: 'percent',
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
  signDisplay: 'always',
});

export function formatSignedPercent(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  return SIGNED_PERCENT_FMT.format(value);
}

const DATE_FMT = new Intl.DateTimeFormat('zh-CN', {
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

export function formatMatchDate(iso: string): string {
  try {
    return DATE_FMT.format(new Date(iso));
  } catch {
    return iso;
  }
}

/** "¥29.90" from 2990 fen. */
export function formatPriceCny(fen: number): string {
  const yuan = fen / 100;
  return new Intl.NumberFormat('zh-CN', {
    style: 'currency',
    currency: 'CNY',
    minimumFractionDigits: yuan === Math.round(yuan) ? 0 : 2,
  }).format(yuan);
}

/** "$9.99" from 999 USD cents. */
export function formatPriceUsd(cents: number): string {
  const dollars = cents / 100;
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: dollars === Math.round(dollars) ? 0 : 2,
  }).format(dollars);
}

// --- Subscription / signal helpers --------------------------------------

const TIER_RANK: Record<SubscriptionTier, number> = { free: 0, basic: 1, premium: 2 };

export function tierMeets(actual: SubscriptionTier, required: SubscriptionTier): boolean {
  return TIER_RANK[actual] >= TIER_RANK[required];
}

export function signalStars(level: SignalLevel | null | undefined): string {
  if (!level || level <= 0) return '';
  return '⭐'.repeat(Math.min(level, 3));
}

// --- Misc ----------------------------------------------------------------

/** Clamp a probability to [0, 1] for safe rendering even with bad payloads. */
export function clampProb(value: number | null | undefined): number {
  if (value == null || Number.isNaN(value)) return 0;
  if (value < 0) return 0;
  if (value > 1) return 1;
  return value;
}
