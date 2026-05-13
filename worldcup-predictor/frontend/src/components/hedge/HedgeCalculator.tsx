'use client';

import { AxiosError } from 'axios';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useState, useTransition } from 'react';

import { Button } from '@/components/ui/Button';
import { Card, CardBody } from '@/components/ui/Card';
import { useAuth } from '@/hooks/useAuth';
import { useSubscription } from '@/hooks/useSubscription';
import { useT } from '@/i18n/I18nProvider';
import { createScenario } from '@/lib/hedgeApi';
import { cn } from '@/lib/utils';
import type { CreateScenarioRequest, ScenarioResponse } from '@/types/hedge';

import { HedgeResultPanel } from './HedgeResultPanel';
import { ParlayHedgeForm } from './ParlayHedgeForm';
import { SingleHedgeForm } from './SingleHedgeForm';

const HEDGE_DISCLAIMER =
  '本平台仅提供数据分析参考,不构成任何投注建议。' +
  '对冲计算器为数学工具,计算结果仅供参考,请用户自行判断。';

/**
 * Top-level orchestrator for the hedge calculator page.
 *
 * Routes single / parlay via the `?type=` query param so the URL is
 * shareable and copy-pastable without losing form state mode.
 */
export function HedgeCalculator() {
  const t = useT();
  const router = useRouter();
  const params = useSearchParams();
  const { user, isAuthenticated } = useAuth();
  const { isPremium } = useSubscription();

  const tab: 'single' | 'parlay' = params.get('type') === 'parlay' ? 'parlay' : 'single';
  const [scenario, setScenario] = useState<ScenarioResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  // useTransition powers the smooth tab swap without re-mounting forms.
  const [, startTransition] = useTransition();

  // ---- Auth + tier gates -------------------------------------------------

  if (!isAuthenticated || !user) {
    return (
      <Card>
        <CardBody className="space-y-4 text-center">
          <p className="text-slate-200">{t('hedge.loginRequired')}</p>
          <Button onClick={() => router.push('/login')}>
            {t('nav.login')}
          </Button>
        </CardBody>
      </Card>
    );
  }

  if (!isPremium) {
    return <UpgradePrompt />;
  }

  // ---- Submit handler ----------------------------------------------------

  const onSubmit = async (req: CreateScenarioRequest) => {
    setIsSubmitting(true);
    setError(null);
    try {
      const result = await createScenario(req);
      setScenario(result);
    } catch (e) {
      const ax = e as AxiosError<{ message?: string }>;
      const msg =
        ax.response?.data?.message ?? ax.message ?? 'Unexpected error';
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const switchTab = (next: 'single' | 'parlay') => {
    if (next === tab) return;
    setScenario(null);
    setError(null);
    startTransition(() => {
      router.replace(`/hedge?type=${next}`);
    });
  };

  return (
    <div className="space-y-6">
      <header className="space-y-1.5">
        <h1 className="text-2xl font-bold text-slate-100">{t('hedge.pageTitle')}</h1>
        <p className="text-sm text-slate-400">{t('hedge.pageSubtitle')}</p>
      </header>

      <DisclaimerBanner />

      <nav
        aria-label="Hedge type"
        className="inline-flex rounded-lg border border-slate-700 bg-slate-900/40 p-1"
      >
        {(['single', 'parlay'] as const).map((k) => (
          <button
            key={k}
            onClick={() => switchTab(k)}
            type="button"
            aria-pressed={tab === k}
            className={cn(
              'rounded-md px-3 py-1.5 text-sm transition-colors',
              tab === k
                ? 'bg-brand-500 text-slate-950'
                : 'text-slate-300 hover:bg-slate-800',
            )}
          >
            {t(`hedge.tabs.${k}`)}
          </button>
        ))}
      </nav>

      {tab === 'single' ? (
        <SingleHedgeForm onSubmit={onSubmit} isSubmitting={isSubmitting} />
      ) : (
        <ParlayHedgeForm onSubmit={onSubmit} isSubmitting={isSubmitting} />
      )}

      {error && (
        <Card>
          <CardBody>
            <p className="text-sm text-rose-400" role="alert">
              {error}
            </p>
          </CardBody>
        </Card>
      )}

      {scenario && <HedgeResultPanel scenario={scenario} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Subcomponents
// ---------------------------------------------------------------------------

function DisclaimerBanner() {
  const t = useT();
  return (
    <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-3 text-xs text-amber-200/90">
      <p className="font-semibold text-amber-200">{t('hedge.disclaimerTitle')}</p>
      <p className="mt-1 leading-relaxed">{HEDGE_DISCLAIMER}</p>
    </div>
  );
}

function UpgradePrompt() {
  const t = useT();
  return (
    <Card>
      <CardBody className="space-y-3 text-center">
        <h2 className="text-lg font-semibold text-slate-100">
          {t('hedge.premiumOnlyBanner')}
        </h2>
        <p className="text-sm text-slate-400">{t('hedge.pageSubtitle')}</p>
        <div className="flex flex-wrap items-center justify-center gap-2">
          <Link
            href="/subscribe"
            className="rounded-xl bg-brand-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-brand-400"
          >
            {t('hedge.premiumOnlyUpgrade')}
          </Link>
          <Link
            href="/about"
            className="rounded-xl border border-slate-700 px-4 py-2 text-sm font-semibold text-slate-200 hover:bg-slate-800"
          >
            {t('hedge.premiumOnlyLearn')}
          </Link>
        </div>
      </CardBody>
    </Card>
  );
}
