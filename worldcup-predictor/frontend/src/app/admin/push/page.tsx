'use client';

import { useState } from 'react';
import useSWR from 'swr';

import { useT } from '@/i18n/I18nProvider';

type Row = {
  id: number;
  user_id: number;
  channel: string;
  notification_type: string;
  title: string;
  status: string;
  sent_at: string | null;
  created_at: string;
};
type Resp = { total: number; items: Row[] };
type Summary = { pending: number; sent_24h: number; failed_24h: number; click_through_24h: number };

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

export default function AdminPushPage() {
  const t = useT();
  const [offset, setOffset] = useState(0);
  const summary = useSWR<Summary>('/api/v1/admin/push/summary', fetcher, { revalidateOnFocus: false });
  const list = useSWR<Resp>(
    `/api/v1/admin/push?limit=${PAGE_SIZE}&offset=${offset}`,
    fetcher,
    { revalidateOnFocus: false },
  );

  if (list.error || summary.error) {
    const e = (list.error || summary.error) as Error;
    return (
      <div className="rounded-md border border-red-200 bg-red-50 p-4 text-red-700">
        {t('admin.common.error')}: {e.message}
      </div>
    );
  }
  if (!list.data || !summary.data) {
    return <div className="text-sm text-slate-400">{t('admin.common.loading')}</div>;
  }

  const total = list.data.total;
  const page = Math.floor(offset / PAGE_SIZE) + 1;

  const cards = [
    { label: t('admin.push.summary.pending'), value: summary.data.pending },
    { label: t('admin.push.summary.sent24h'), value: summary.data.sent_24h },
    { label: t('admin.push.summary.failed24h'), value: summary.data.failed_24h },
    { label: t('admin.push.summary.ctr24h'), value: summary.data.click_through_24h },
  ];

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-base font-semibold text-slate-200">{t('admin.push.title')}</h2>
        <p className="mt-1 text-xs text-slate-400">{t('admin.push.description')}</p>
      </div>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {cards.map((c) => (
          <div key={c.label} className="rounded-md surface-card p-4">
            <div className="text-xs text-slate-400">{c.label}</div>
            <div className="mt-1 text-2xl font-semibold text-slate-100">{c.value.toLocaleString()}</div>
          </div>
        ))}
      </div>
      <div className="rounded-md surface-card">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-900/50 text-left text-xs uppercase text-slate-400">
              <th className="px-4 py-2">{t('admin.push.columns.id')}</th>
              <th className="px-4 py-2">{t('admin.push.columns.user')}</th>
              <th className="px-4 py-2">{t('admin.push.columns.channel')}</th>
              <th className="px-4 py-2">{t('admin.push.columns.type')}</th>
              <th className="px-4 py-2">{t('admin.push.columns.title')}</th>
              <th className="px-4 py-2">{t('admin.push.columns.status')}</th>
              <th className="px-4 py-2">{t('admin.push.columns.createdAt')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/70">
            {list.data.items.map((n) => (
              <tr key={n.id}>
                <td className="px-4 py-2 text-slate-300">{n.id}</td>
                <td className="px-4 py-2 text-slate-300">#{n.user_id}</td>
                <td className="px-4 py-2 text-slate-300">{n.channel}</td>
                <td className="px-4 py-2 text-slate-300">{n.notification_type}</td>
                <td className="px-4 py-2 text-slate-300">{n.title}</td>
                <td className="px-4 py-2 text-slate-300">{n.status}</td>
                <td className="px-4 py-2 text-slate-400">{new Date(n.created_at).toLocaleString()}</td>
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
    </div>
  );
}
