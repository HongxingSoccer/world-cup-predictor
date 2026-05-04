'use client';

import { useState } from 'react';
import useSWR from 'swr';

import { useT } from '@/i18n/I18nProvider';

type LogRow = {
  id: number;
  source_name: string;
  task_type: string;
  status: string;
  records_fetched: number | null;
  records_inserted: number | null;
  started_at: string;
  finished_at: string | null;
  error_message: string | null;
};
type LogResp = { total: number; items: LogRow[] };
type SummaryRow = {
  source_name: string;
  last_run_at: string | null;
  last_status: string | null;
  success_24h: number;
  failed_24h: number;
};
type SummaryResp = { sources: SummaryRow[] };

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

export default function AdminDataSourcesPage() {
  const t = useT();
  const [offset, setOffset] = useState(0);
  const summary = useSWR<SummaryResp>('/api/v1/admin/data-sources/summary', fetcher, {
    revalidateOnFocus: false,
  });
  const logs = useSWR<LogResp>(
    `/api/v1/admin/data-sources?limit=${PAGE_SIZE}&offset=${offset}`,
    fetcher,
    { revalidateOnFocus: false },
  );

  if (logs.error || summary.error) {
    const e = (logs.error || summary.error) as Error;
    return (
      <div className="rounded-md border border-red-200 bg-red-50 p-4 text-red-700">
        {t('admin.common.error')}: {e.message}
      </div>
    );
  }
  if (!logs.data || !summary.data) {
    return <div className="text-sm text-slate-500">{t('admin.common.loading')}</div>;
  }

  const total = logs.data.total;
  const page = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <div className="space-y-4">
      <div className="rounded-md border border-slate-200 bg-white">
        <div className="border-b border-slate-100 p-4">
          <h2 className="text-base font-semibold text-slate-800">{t('admin.dataSources.title')}</h2>
          <p className="mt-1 text-xs text-slate-500">{t('admin.dataSources.description')}</p>
        </div>
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <th className="px-4 py-2">{t('admin.dataSources.summary.source')}</th>
              <th className="px-4 py-2">{t('admin.dataSources.summary.lastRun')}</th>
              <th className="px-4 py-2">{t('admin.dataSources.summary.lastStatus')}</th>
              <th className="px-4 py-2">{t('admin.dataSources.summary.success24h')}</th>
              <th className="px-4 py-2">{t('admin.dataSources.summary.failed24h')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {summary.data.sources.map((s) => (
              <tr key={s.source_name}>
                <td className="px-4 py-2 text-slate-700">{s.source_name}</td>
                <td className="px-4 py-2 text-slate-500">
                  {s.last_run_at ? new Date(s.last_run_at).toLocaleString() : '—'}
                </td>
                <td className="px-4 py-2 text-slate-700">{s.last_status ?? '—'}</td>
                <td className="px-4 py-2 text-emerald-600">{s.success_24h}</td>
                <td className="px-4 py-2 text-red-600">{s.failed_24h}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="rounded-md border border-slate-200 bg-white">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <th className="px-4 py-2">{t('admin.dataSources.columns.id')}</th>
              <th className="px-4 py-2">{t('admin.dataSources.columns.source')}</th>
              <th className="px-4 py-2">{t('admin.dataSources.columns.task')}</th>
              <th className="px-4 py-2">{t('admin.dataSources.columns.status')}</th>
              <th className="px-4 py-2">{t('admin.dataSources.columns.fetched')}</th>
              <th className="px-4 py-2">{t('admin.dataSources.columns.inserted')}</th>
              <th className="px-4 py-2">{t('admin.dataSources.columns.startedAt')}</th>
              <th className="px-4 py-2">{t('admin.dataSources.columns.finishedAt')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {logs.data.items.map((l) => (
              <tr key={l.id}>
                <td className="px-4 py-2 text-slate-700">{l.id}</td>
                <td className="px-4 py-2 text-slate-700">{l.source_name}</td>
                <td className="px-4 py-2 text-slate-700">{l.task_type}</td>
                <td className="px-4 py-2 text-slate-700">{l.status}</td>
                <td className="px-4 py-2 text-slate-700">{l.records_fetched ?? '—'}</td>
                <td className="px-4 py-2 text-slate-700">{l.records_inserted ?? '—'}</td>
                <td className="px-4 py-2 text-slate-500">{new Date(l.started_at).toLocaleString()}</td>
                <td className="px-4 py-2 text-slate-500">
                  {l.finished_at ? new Date(l.finished_at).toLocaleString() : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3 text-xs text-slate-500">
          <span>
            {t('admin.common.total').replace('{n}', String(total))} ·{' '}
            {t('admin.common.page').replace('{n}', String(page))}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded-md border border-slate-200 px-3 py-1 disabled:opacity-50"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              aria-label="prev-page"
            >
              {t('admin.common.prev')}
            </button>
            <button
              type="button"
              className="rounded-md border border-slate-200 px-3 py-1 disabled:opacity-50"
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
