'use client';

import { useEffect } from 'react';

import { Button } from '@/components/ui/Button';
import { useT } from '@/i18n/I18nProvider';

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

/**
 * App-level error boundary. Renders inside the root layout (with header /
 * footer), so it inherits the dark gradient + chrome — only the body slot
 * swaps out for this fallback.
 *
 * Side-effect: posts the digest to ml-api's `/client-errors` sentinel so
 * we have server-side breadcrumb when a user reports a problem. The POST
 * is fire-and-forget — failure to phone home never blocks the UI.
 */
export default function GlobalErrorBoundary({ error, reset }: ErrorProps) {
  const t = useT();
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (error.digest) {
      console.error('[error.tsx]', error.digest, error.message);
    }
    // Same rationale as `lib/api.ts`: relative URLs go to the same nginx
    // origin and avoid CORS. Override with NEXT_PUBLIC_API_URL only for
    // off-domain deployments.
    const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? '';
    const payload = {
      digest: error.digest ?? null,
      pathname: window.location.pathname,
      message: error.message?.slice(0, 2000) ?? null,
    };
    // The endpoint is whitelisted in the API-key middleware so anonymous
    // browsers can post directly. We swallow any network error — the
    // boundary already showed the user a helpful message.
    fetch(`${baseUrl}/api/v1/client-errors`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      keepalive: true,
    }).catch(() => undefined);
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center px-4 text-center">
      <div className="hero-number text-7xl font-black sm:text-8xl">500</div>
      <h1 className="mt-3 text-xl font-bold text-slate-100">{t('error.title')}</h1>
      <p className="mt-2 max-w-sm text-sm leading-relaxed text-slate-400">{t('error.body')}</p>
      {error.digest ? (
        <p className="mt-2 text-[11px] font-mono tabular-nums text-slate-500">
          {t('error.errorNo')} {error.digest}
        </p>
      ) : null}
      <div className="mt-6 flex flex-wrap gap-3">
        <Button onClick={() => reset()}>{t('common.retry')}</Button>
        <Button variant="ghost" onClick={() => (window.location.href = '/')}>
          {t('common.backHome')}
        </Button>
      </div>
    </div>
  );
}
