'use client';

import { Shield } from 'lucide-react';
import Link from 'next/link';
import useSWR from 'swr';

import { useT } from '@/i18n/I18nProvider';

type AdminCard = { label: string; value: number; delta_24h?: number | null };
type OverviewResponse = { cards: AdminCard[]; generated_at: string };

const fetcher = (url: string) =>
  fetch(url, {
    headers: { 'X-Admin-Token': adminToken() },
  }).then((r) => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  });

function adminToken(): string {
  if (typeof window === 'undefined') return '';
  return window.localStorage.getItem('wcp_admin_token') ?? '';
}

export default function AdminOverviewPage() {
  const t = useT();
  const { data, error, isLoading } = useSWR<OverviewResponse>('/api/v1/admin', fetcher, {
    revalidateOnFocus: false,
  });

  if (error) {
    const status = (error as Error).message.match(/HTTP (\d+)/)?.[1];
    const isAuthError = status === '401' || status === '404';
    return (
      <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-5 text-rose-200">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <Shield size={16} />
          {isAuthError ? '管理员令牌缺失或已失效' : '加载失败'}
        </div>
        <div className="mt-2 text-xs text-rose-300/80">
          {(error as Error).message}
        </div>
        {isAuthError ? (
          <Link
            href="/admin/login"
            className="mt-3 inline-flex items-center rounded-lg bg-rose-500/20 px-3 py-1.5 text-xs font-semibold text-rose-100 hover:bg-rose-500/30"
          >
            前往设置令牌 →
          </Link>
        ) : null}
      </div>
    );
  }
  if (isLoading || !data) {
    return (
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-24 animate-pulse rounded-2xl bg-slate-800/60" />
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
      {data.cards.map((c) => (
        <div key={c.label} className="surface-card rounded-2xl p-4">
          <div className="text-xs uppercase tracking-wider text-slate-400">
            {t(`admin.cards.${c.label}`, c.label)}
          </div>
          <div className="mt-1 hero-number text-3xl font-bold tabular-nums">
            {c.value.toLocaleString()}
          </div>
          {c.delta_24h != null ? (
            <div className="mt-1 text-xs text-emerald-300">
              +<span className="tabular-nums">{c.delta_24h}</span> (24h)
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}
