'use client';

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
    return (
      <div className="rounded-md border border-red-200 bg-red-50 p-4 text-red-700">
        Failed to load admin overview: {(error as Error).message}
      </div>
    );
  }
  if (isLoading || !data) {
    return <div className="text-sm text-slate-500">{t('common.loading')}</div>;
  }

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
      {data.cards.map((c) => (
        <div key={c.label} className="rounded-md border border-slate-200 bg-white p-4">
          <div className="text-xs text-slate-500">{t(`admin.cards.${c.label}`, c.label)}</div>
          <div className="mt-1 text-2xl font-semibold text-slate-900">
            {c.value.toLocaleString()}
          </div>
          {c.delta_24h != null && (
            <div className="mt-1 text-xs text-emerald-600">+{c.delta_24h} (24h)</div>
          )}
        </div>
      ))}
    </div>
  );
}
