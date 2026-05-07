'use client';

import { useState } from 'react';
import useSWR from 'swr';

import { useT } from '@/i18n/I18nProvider';

type Row = {
  id: number;
  user_id: number;
  user_email: string | null;
  tier: string;
  plan_type: string;
  status: string;
  price_cny: number;
  started_at: string;
  expires_at: string;
};
type Resp = { total: number; items: Row[] };

function adminToken(): string {
  if (typeof window === 'undefined') return '';
  return window.localStorage.getItem('wcp_admin_token') ?? '';
}

const fetcher = (url: string) =>
  fetch(url, { headers: { 'X-Admin-Token': adminToken() } }).then((r) => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  });

const PAGE_SIZE = 20;

export default function AdminSubscriptionsPage() {
  const t = useT();
  const [offset, setOffset] = useState(0);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const qs = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
  if (statusFilter) qs.set('status', statusFilter);
  const { data, error, isLoading } = useSWR<Resp>(
    `/api/v1/admin/subscriptions?${qs.toString()}`,
    fetcher,
    { revalidateOnFocus: false },
  );

  if (error) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 p-4 text-red-700">
        {t('admin.common.error')}: {(error as Error).message}
      </div>
    );
  }
  if (isLoading || !data) return <div className="text-sm text-slate-400">{t('admin.common.loading')}</div>;

  const total = data.total;
  const page = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <div className="rounded-md surface-card">
      <div className="flex items-center justify-between border-b border-slate-800/70 p-4">
        <div>
          <h2 className="text-base font-semibold text-slate-200">{t('admin.subscriptions.title')}</h2>
          <p className="mt-1 text-xs text-slate-400">{t('admin.subscriptions.description')}</p>
        </div>
        <div className="flex gap-1 text-xs">
          {[
            { v: '', label: t('admin.subscriptions.filterAll') },
            { v: 'active', label: t('admin.subscriptions.filterActive') },
            { v: 'expired', label: t('admin.subscriptions.filterExpired') },
          ].map((opt) => (
            <button
              key={opt.v}
              type="button"
              onClick={() => {
                setStatusFilter(opt.v);
                setOffset(0);
              }}
              className={`rounded-md px-2 py-1 ${
                statusFilter === opt.v ? 'bg-emerald-50 text-emerald-700' : 'text-slate-400 hover:bg-slate-900/50'
              }`}
              aria-label={`filter-${opt.v || 'all'}`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-slate-900/50 text-left text-xs uppercase text-slate-400">
            <th className="px-4 py-2">{t('admin.subscriptions.columns.id')}</th>
            <th className="px-4 py-2">{t('admin.subscriptions.columns.user')}</th>
            <th className="px-4 py-2">{t('admin.subscriptions.columns.tier')}</th>
            <th className="px-4 py-2">{t('admin.subscriptions.columns.plan')}</th>
            <th className="px-4 py-2">{t('admin.subscriptions.columns.status')}</th>
            <th className="px-4 py-2">{t('admin.subscriptions.columns.price')}</th>
            <th className="px-4 py-2">{t('admin.subscriptions.columns.started')}</th>
            <th className="px-4 py-2">{t('admin.subscriptions.columns.expires')}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/70">
          {data.items.map((s) => (
            <tr key={s.id}>
              <td className="px-4 py-2 text-slate-300">{s.id}</td>
              <td className="px-4 py-2 text-slate-300">{s.user_email ?? `#${s.user_id}`}</td>
              <td className="px-4 py-2 text-slate-300">{s.tier}</td>
              <td className="px-4 py-2 text-slate-300">{s.plan_type}</td>
              <td className="px-4 py-2 text-slate-300">{s.status}</td>
              <td className="px-4 py-2 text-slate-300">¥{(s.price_cny / 100).toFixed(2)}</td>
              <td className="px-4 py-2 text-slate-400">{new Date(s.started_at).toLocaleString()}</td>
              <td className="px-4 py-2 text-slate-400">{new Date(s.expires_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex items-center justify-between border-t border-slate-800/70 px-4 py-3 text-xs text-slate-400">
        <span>
          {t('admin.common.total').replace('{n}', String(total))} ·{' '}
          {t('admin.common.page').replace('{n}', String(page))}
        </span>
        <div className="flex gap-2">
          <button
            type="button"
            className="rounded-md border border-slate-800/70 px-3 py-1 disabled:opacity-50"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            aria-label="prev-page"
          >
            {t('admin.common.prev')}
          </button>
          <button
            type="button"
            className="rounded-md border border-slate-800/70 px-3 py-1 disabled:opacity-50"
            disabled={offset + PAGE_SIZE >= total}
            onClick={() => setOffset(offset + PAGE_SIZE)}
            aria-label="next-page"
          >
            {t('admin.common.next')}
          </button>
        </div>
      </div>
    </div>
  );
}
