'use client';

import { useState } from 'react';
import useSWR from 'swr';

import { useT } from '@/i18n/I18nProvider';

type Row = {
  id: number;
  match_id: number;
  model_version: string;
  confidence_score: number;
  confidence_level: string;
  published_at: string;
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

export default function AdminPredictionsPage() {
  const t = useT();
  const [offset, setOffset] = useState(0);
  const { data, error, isLoading } = useSWR<Resp>(
    `/api/v1/admin/predictions?limit=${PAGE_SIZE}&offset=${offset}`,
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
      <div className="border-b border-slate-800/70 p-4">
        <h2 className="text-base font-semibold text-slate-200">{t('admin.predictions.title')}</h2>
        <p className="mt-1 text-xs text-slate-400">{t('admin.predictions.description')}</p>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-slate-900/50 text-left text-xs uppercase text-slate-400">
            <th className="px-4 py-2">{t('admin.predictions.columns.id')}</th>
            <th className="px-4 py-2">{t('admin.predictions.columns.match')}</th>
            <th className="px-4 py-2">{t('admin.predictions.columns.model')}</th>
            <th className="px-4 py-2">{t('admin.predictions.columns.confidence')}</th>
            <th className="px-4 py-2">{t('admin.predictions.columns.publishedAt')}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/70">
          {data.items.map((p) => (
            <tr key={p.id}>
              <td className="px-4 py-2 text-slate-300">{p.id}</td>
              <td className="px-4 py-2 text-slate-300">{p.match_id}</td>
              <td className="px-4 py-2 text-slate-300">{p.model_version}</td>
              <td className="px-4 py-2 text-slate-300">
                {p.confidence_score} ({p.confidence_level})
              </td>
              <td className="px-4 py-2 text-slate-400">{new Date(p.published_at).toLocaleString()}</td>
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
