'use client';

import { useState } from 'react';
import useSWR from 'swr';

import { useT } from '@/i18n/I18nProvider';

type UserRow = {
  id: number;
  uuid: string;
  email: string | null;
  subscription_tier: string;
  created_at: string;
};
type Resp = { total: number; items: UserRow[] };

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

export default function AdminUsersPage() {
  const t = useT();
  const [offset, setOffset] = useState(0);
  const { data, error, isLoading } = useSWR<Resp>(
    `/api/v1/admin/users?limit=${PAGE_SIZE}&offset=${offset}`,
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
  if (isLoading || !data) return <div className="text-sm text-slate-500">{t('admin.common.loading')}</div>;

  const total = data.total;
  const page = Math.floor(offset / PAGE_SIZE) + 1;

  return (
    <div className="rounded-md border border-slate-200 bg-white">
      <div className="border-b border-slate-100 p-4">
        <h2 className="text-base font-semibold text-slate-800">{t('admin.users.title')}</h2>
        <p className="mt-1 text-xs text-slate-500">{t('admin.users.description')}</p>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <th className="px-4 py-2">{t('admin.users.columns.id')}</th>
            <th className="px-4 py-2">{t('admin.users.columns.email')}</th>
            <th className="px-4 py-2">{t('admin.users.columns.tier')}</th>
            <th className="px-4 py-2">{t('admin.users.columns.createdAt')}</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {data.items.map((u) => (
            <tr key={u.id}>
              <td className="px-4 py-2 text-slate-700">{u.id}</td>
              <td className="px-4 py-2 text-slate-700">{u.email ?? '—'}</td>
              <td className="px-4 py-2 text-slate-700">{u.subscription_tier}</td>
              <td className="px-4 py-2 text-slate-500">{new Date(u.created_at).toLocaleString()}</td>
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
  );
}
