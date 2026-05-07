'use client';

import { useEffect } from 'react';

import { Button } from '@/components/ui/Button';

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

/**
 * App-level error boundary. Renders inside the root layout (with header /
 * footer), so it inherits the dark gradient + chrome — only the body slot
 * swaps out for this fallback.
 */
export default function GlobalErrorBoundary({ error, reset }: ErrorProps) {
  useEffect(() => {
    // Surface the digest in the console so it's easy to grep for in the
    // server logs when a user reports a problem.
    if (typeof window !== 'undefined' && error.digest) {
      console.error('[error.tsx]', error.digest, error.message);
    }
  }, [error]);

  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center px-4 text-center">
      <div className="hero-number text-7xl font-black sm:text-8xl">500</div>
      <h1 className="mt-3 text-xl font-bold text-slate-100">出了点问题</h1>
      <p className="mt-2 max-w-sm text-sm leading-relaxed text-slate-400">
        服务器在处理这个请求时遇到错误。我们已经记录此事件，工程师会跟进。
      </p>
      {error.digest ? (
        <p className="mt-2 text-[11px] font-mono tabular-nums text-slate-500">
          错误编号 · {error.digest}
        </p>
      ) : null}
      <div className="mt-6 flex flex-wrap gap-3">
        <Button onClick={() => reset()}>重试</Button>
        <Button variant="ghost" onClick={() => (window.location.href = '/')}>
          回到首页
        </Button>
      </div>
    </div>
  );
}
