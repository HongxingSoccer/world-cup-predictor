'use client';

import { Shield } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';

const STORAGE_KEY = 'wcp_admin_token';

/**
 * Token entry for the admin console. The admin endpoints are gated by
 * X-Admin-Token (read from localStorage). Until now there was no UI to
 * set it — operators had to paste into devtools. This is that UI.
 *
 * Pure client-side: no backend call. The token is validated implicitly
 * on the next admin request (a bad token returns 401 there).
 */
export default function AdminLoginPage() {
  const router = useRouter();
  const [token, setToken] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = token.trim();
    if (!trimmed) return;
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEY, trimmed);
    }
    setSubmitted(true);
    router.push('/admin');
  };

  const onClear = () => {
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(STORAGE_KEY);
    }
    setToken('');
    setSubmitted(false);
  };

  return (
    <div className="mx-auto max-w-md">
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Shield size={16} className="text-amber-300" />
            <h1 className="text-base font-semibold text-slate-100">管理员令牌</h1>
          </div>
        </CardHeader>
        <CardBody className="space-y-4">
          <p className="text-xs leading-relaxed text-slate-400">
            粘贴运维分发的 <code className="rounded bg-slate-800/70 px-1 text-cyan-300">ADMIN_API_TOKEN</code>{' '}
            到下方，浏览器本地保存，仅用于发送 <code className="rounded bg-slate-800/70 px-1 text-cyan-300">X-Admin-Token</code>{' '}
            请求头。错误的令牌会在下个请求被服务端 401 拒绝。
          </p>
          <form onSubmit={onSubmit} className="space-y-3">
            <input
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              placeholder="paste token here"
              className="w-full rounded-md border border-slate-700 bg-slate-900/70 px-3 py-2 text-sm text-slate-100 outline-none focus:border-cyan-400/60"
              autoFocus
              autoComplete="off"
            />
            <div className="flex gap-2">
              <Button type="submit" disabled={!token.trim()}>
                保存并进入管理台
              </Button>
              <Button type="button" variant="ghost" onClick={onClear}>
                清除已保存
              </Button>
            </div>
          </form>
          {submitted ? (
            <p className="text-xs text-emerald-300">已保存，正在跳转…</p>
          ) : null}
        </CardBody>
      </Card>
    </div>
  );
}
