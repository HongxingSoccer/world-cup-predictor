'use client';

import { useState } from 'react';
import useSWR from 'swr';

import { useT } from '@/i18n/I18nProvider';

type Row = {
  id: number;
  match_id: number;
  title: string;
  summary: string;
  model_used: string;
  status: string;
  generated_at: string;
  published_at: string | null;
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

async function moderate(id: number, action: 'publish' | 'reject') {
  const res = await fetch(`/api/v1/admin/reports/${id}/${action}`, {
    method: 'POST',
    headers: { 'X-Admin-Token': adminToken() },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

const PAGE_SIZE = 20;

export default function AdminContentPage() {
  const t = useT();
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState<number | null>(null);
  const { data, error, isLoading, mutate } = useSWR<Resp>(
    `/api/v1/admin/content/moderation?limit=${PAGE_SIZE}&offset=${offset}`,
    fetcher,
    { revalidateOnFocus: false },
  );

  const onAction = async (id: number, action: 'publish' | 'reject') => {
    setBusy(id);
    try {
      await moderate(id, action);
      await mutate();
    } finally {
      setBusy(null);
    }
  };

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
      <div className="border-b border-slate-800/70 p-4">
        <h2 className="text-base font-semibold text-slate-200">{t('admin.content.title')}</h2>
        <p className="mt-1 text-xs text-slate-400">{t('admin.content.description')}</p>
      </div>
      {data.items.length === 0 ? (
        <div className="px-4 py-8 text-center text-sm text-slate-400">{t('admin.content.queueEmpty')}</div>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-900/50 text-left text-xs uppercase text-slate-400">
              <th className="px-4 py-2">{t('admin.reports.columns.id')}</th>
              <th className="px-4 py-2">{t('admin.reports.columns.match')}</th>
              <th className="px-4 py-2">{t('admin.reports.columns.title')}</th>
              <th className="px-4 py-2">{t('admin.reports.columns.model')}</th>
              <th className="px-4 py-2">{t('admin.reports.columns.generatedAt')}</th>
              <th className="px-4 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/70">
            {data.items.map((r) => (
              <tr key={r.id}>
                <td className="px-4 py-2 text-slate-300">{r.id}</td>
                <td className="px-4 py-2 text-slate-300">{r.match_id}</td>
                <td className="px-4 py-2 text-slate-300">{r.title}</td>
                <td className="px-4 py-2 text-slate-300">{r.model_used}</td>
                <td className="px-4 py-2 text-slate-400">{new Date(r.generated_at).toLocaleString()}</td>
                <td className="px-4 py-2 text-right">
                  <div className="flex justify-end gap-2">
                    <button
                      type="button"
                      disabled={busy === r.id}
                      onClick={() => onAction(r.id, 'publish')}
                      className="rounded-md bg-emerald-500 px-2 py-1 text-xs text-white disabled:opacity-40"
                      aria-label={`publish-${r.id}`}
                    >
                      {t('admin.reports.publish')}
                    </button>
                    <button
                      type="button"
                      disabled={busy === r.id}
                      onClick={() => onAction(r.id, 'reject')}
                      className="rounded-md border border-slate-700 px-2 py-1 text-xs text-slate-300 disabled:opacity-40"
                      aria-label={`reject-${r.id}`}
                    >
                      {t('admin.reports.reject')}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
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
