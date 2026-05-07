'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { useAuthStore } from '@/stores/auth-store';
import { cn } from '@/lib/utils';

type Tab = 'login' | 'register';

export default function LoginPage() {
  const router = useRouter();
  const login = useAuthStore((s) => s.login);
  const register = useAuthStore((s) => s.register);

  const [tab, setTab] = useState<Tab>('login');
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [nickname, setNickname] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const looksLikeEmail = identifier.includes('@');

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const args = looksLikeEmail
        ? { email: identifier, password }
        : { phone: identifier, password };
      if (tab === 'login') {
        await login(args);
      } else {
        await register({ ...args, nickname: nickname || undefined });
      }
      router.push('/profile');
    } catch (err) {
      const message = err instanceof Error ? err.message : '认证失败';
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-md space-y-4">
      <div className="grid grid-cols-2 rounded-2xl bg-slate-800/70 p-1">
        {(['login', 'register'] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={cn(
              'rounded-xl py-2 text-sm font-semibold',
              tab === t ? 'bg-slate-900/70 text-slate-100 shadow' : 'text-slate-400',
            )}
          >
            {t === 'login' ? '登录' : '注册'}
          </button>
        ))}
      </div>

      <Card>
        <CardHeader>
          <h1 className="text-base font-semibold text-slate-100">
            {tab === 'login' ? '欢迎回来' : '创建新账户'}
          </h1>
        </CardHeader>
        <CardBody>
          <form onSubmit={onSubmit} className="space-y-3">
            <Field label="手机号或邮箱">
              <input
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder="13800138000 或 you@example.com"
                className="input"
                autoComplete="username"
                required
              />
            </Field>
            <Field label="密码">
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="至少 8 位"
                className="input"
                autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
                minLength={8}
                required
              />
            </Field>
            {tab === 'register' ? (
              <Field label="昵称（可选）">
                <input
                  value={nickname}
                  onChange={(e) => setNickname(e.target.value)}
                  className="input"
                  maxLength={50}
                />
              </Field>
            ) : null}
            {error ? (
              <div className="rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>
            ) : null}
            <Button type="submit" loading={submitting} className="w-full">
              {tab === 'login' ? '登录' : '注册并登录'}
            </Button>
          </form>

          <div className="my-4 flex items-center gap-3 text-xs text-slate-400">
            <div className="h-px flex-1 bg-slate-700/70" />
            或使用第三方登录
            <div className="h-px flex-1 bg-slate-700/70" />
          </div>

          <Button variant="secondary" className="w-full" disabled>
            微信登录（即将推出）
          </Button>
        </CardBody>
      </Card>

      <style jsx>{`
        .input {
          width: 100%;
          border-radius: 0.75rem;
          border: 1px solid rgb(226 232 240);
          padding: 0.5rem 0.75rem;
          font-size: 0.875rem;
          outline: none;
          transition: border 0.15s;
        }
        .input:focus {
          border-color: rgb(22 163 74);
        }
      `}</style>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-slate-400">{label}</span>
      {children}
    </label>
  );
}
