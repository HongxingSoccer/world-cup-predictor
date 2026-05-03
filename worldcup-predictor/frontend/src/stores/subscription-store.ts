/**
 * Subscription state — derived primarily from the auth-store user, plus a
 * `canAccess(feature)` helper the components call to decide whether to
 * render the paywall.
 *
 * The store is intentionally light: the source of truth is the `User`
 * object's `subscriptionTier` + `subscriptionExpires`. Anything richer
 * (autoRenew toggle, payment history) is fetched on-demand via SWR.
 */
import { create } from 'zustand';

import type { SubscriptionTier } from '@/types';

/** Feature keys gated by tier — keep aligned with `ContentTierService` (Java). */
export type FeatureKey =
  | 'score_matrix'
  | 'over_under'
  | 'odds_analysis'
  | 'value_signal_full'
  | 'xg_panel'
  | 'injuries_panel'
  | 'confidence_filter';

const TIER_RANK: Record<SubscriptionTier, number> = { free: 0, basic: 1, premium: 2 };
const FEATURE_REQUIREMENTS: Record<FeatureKey, SubscriptionTier> = {
  score_matrix:       'basic',
  over_under:         'basic',
  odds_analysis:      'basic',
  value_signal_full:  'basic',
  xg_panel:           'premium',
  injuries_panel:     'premium',
  confidence_filter:  'premium',
};

interface SubscriptionState {
  tier: SubscriptionTier;
  expiresAt: string | null;

  setTier: (tier: SubscriptionTier, expiresAt: string | null) => void;

  /** True iff the current tier covers the given feature. */
  canAccess: (feature: FeatureKey) => boolean;
  isBasic: () => boolean;
  isPremium: () => boolean;
}

export const useSubscriptionStore = create<SubscriptionState>((set, get) => ({
  tier: 'free',
  expiresAt: null,

  setTier: (tier, expiresAt) => set({ tier, expiresAt }),

  canAccess: (feature) => {
    const required = FEATURE_REQUIREMENTS[feature];
    return TIER_RANK[get().tier] >= TIER_RANK[required];
  },

  isBasic: () => TIER_RANK[get().tier] >= TIER_RANK.basic,
  isPremium: () => TIER_RANK[get().tier] >= TIER_RANK.premium,
}));
