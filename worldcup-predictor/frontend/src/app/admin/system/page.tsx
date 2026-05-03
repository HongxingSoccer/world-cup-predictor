'use client';

import { useState } from 'react';
import useSWR from 'swr';

import { useT } from '@/i18n/I18nProvider';

type FlagsResponse = { flags: Record<string, boolean> };

function adminToken(): string {
  if (typeof window === 'undefined') return '';
  return window.localStorage.getItem('wcp_admin_token') ?? '';
}

const fetcher = (url: string) =>
  fetch(url, { headers: { 'X-Admin-Token': adminToken() } }).then((r) => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  });

async function updateFlag(name: string, value: boolean): Promise<FlagsResponse> {
  const res = await fetch('/api/v1/admin/system/flags', {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'X-Admin-Token': adminToken(),
    },
    body: JSON.stringify({ name, value }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export default function AdminSystemPage() {
  const t = useT();
  const { data, error, isLoading, mutate } = useSWR<FlagsResponse>(
    '/api/v1/admin/system/flags',
    fetcher,
    { revalidateOnFocus: false },
  );
  const [updating, setUpdating] = useState<string | null>(null);

  const onToggle = async (name: string, current: boolean) => {
    setUpdating(name);
    try {
      const next = await updateFlag(name, !current);
      await mutate(next, { revalidate: false });
    } finally {
      setUpdating(null);
    }
  };

  if (error) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 p-4 text-red-700">
        Failed to load flags: {(error as Error).message}
      </div>
    );
  }
  if (isLoading || !data) return <div className="text-sm text-slate-500">{t('common.loading')}</div>;

  return (
    <div className="rounded-md border border-slate-200 bg-white">
      <div className="border-b border-slate-100 p-4">
        <h2 className="text-base font-semibold text-slate-800">{t('admin.flags.title')}</h2>
        <p className="mt-1 text-xs text-slate-500">{t('admin.flags.description')}</p>
      </div>
      <ul className="divide-y divide-slate-100">
        {Object.entries(data.flags).map(([name, value]) => (
          <li key={name} className="flex items-center justify-between gap-4 px-4 py-3">
            <code className="text-sm text-slate-700">{name}</code>
            <button
              type="button"
              disabled={updating === name}
              onClick={() => onToggle(name, value)}
              className={`inline-flex h-6 w-11 items-center rounded-full transition ${
                value ? 'bg-emerald-500' : 'bg-slate-300'
              } ${updating === name ? 'opacity-50' : ''}`}
              aria-pressed={value}
              aria-label={`flag-${name}`}
            >
              <span
                className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition ${
                  value ? 'translate-x-5' : 'translate-x-1'
                }`}
              />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
