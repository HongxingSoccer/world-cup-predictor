'use client';

import { useSubscriptionStore, type FeatureKey } from '@/stores/subscription-store';
import type { SubscriptionTier } from '@/types';

interface UseSubscriptionResult {
  tier: SubscriptionTier;
  expiresAt: string | null;
  isBasic: boolean;
  isPremium: boolean;
  canAccess: (feature: FeatureKey) => boolean;
}

export function useSubscription(): UseSubscriptionResult {
  const tier = useSubscriptionStore((s) => s.tier);
  const expiresAt = useSubscriptionStore((s) => s.expiresAt);
  const isBasic = useSubscriptionStore((s) => s.isBasic());
  const isPremium = useSubscriptionStore((s) => s.isPremium());
  const canAccess = useSubscriptionStore((s) => s.canAccess);

  return { tier, expiresAt, isBasic, isPremium, canAccess };
}
