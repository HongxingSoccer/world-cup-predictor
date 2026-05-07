'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { useState } from 'react';

import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { useT } from '@/i18n/I18nProvider';
import { useAuthStore } from '@/stores/auth-store';
import { cn } from '@/lib/utils';

type Tab = 'login' | 'register';

export default function LoginPage() {
  const t = useT();
  const router = useRouter();
  const searchParams = useSearchParams();
  const requiredFromPath = searchParams.get('next');
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
      // Honour ?next=<path> when set by the protected-route redirect.
      const target = requiredFromPath && requiredFromPath.startsWith('/') ? requiredFromPath : '/profile';
      router.push(target as never);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'auth failed';
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-md space-y-4">
      {requiredFromPath ? (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-200">
          {t('auth.loginRequiredToast')}
        </div>
      ) : null}
      <div className="grid grid-cols-2 rounded-2xl bg-slate-800/70 p-1">
        {(['login', 'register'] as const).map((id) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={cn(
              'rounded-xl py-2 text-sm font-semibold',
              tab === id ? 'bg-slate-900/70 text-slate-100 shadow' : 'text-slate-400',
            )}
          >
            {id === 'login' ? t('auth.tabLogin') : t('auth.tabRegister')}
          </button>
        ))}
      </div>

      <Card>
        <CardHeader>
          <h1 className="text-base font-semibold text-slate-100">
            {tab === 'login' ? t('auth.headingLogin') : t('auth.headingRegister')}
          </h1>
        </CardHeader>
        <CardBody>
          <form onSubmit={onSubmit} className="space-y-3">
            <Field label={t('auth.phoneOrEmail')}>
              <input
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder="13800138000 / you@example.com"
                className="input"
                autoComplete="username"
                required
              />
            </Field>
            <Field label={t('auth.password')}>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={t('auth.passwordHint')}
                className="input"
                autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
                minLength={8}
                required
              />
            </Field>
            {tab === 'register' ? (
              <Field label={t('auth.nicknameOptional')}>
                <input
                  value={nickname}
                  onChange={(e) => setNickname(e.target.value)}
                  className="input"
                  maxLength={50}
                />
              </Field>
            ) : null}
            {error ? (
              <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-3 py-2 text-sm text-rose-300">
                {error}
              </div>
            ) : null}
            <Button type="submit" loading={submitting} className="w-full">
              {tab === 'login' ? t('auth.submitLogin') : t('auth.submitRegister')}
            </Button>
          </form>

          <div className="my-4 flex items-center gap-3 text-xs text-slate-400">
            <div className="h-px flex-1 bg-slate-700/70" />
            {t('auth.thirdParty')}
            <div className="h-px flex-1 bg-slate-700/70" />
          </div>

          <Button variant="secondary" className="w-full" disabled>
            {t('auth.wechatComing')}
          </Button>
        </CardBody>
      </Card>

      <style jsx>{`
        .input {
          width: 100%;
          border-radius: 0.75rem;
          border: 1px solid rgb(51 65 85);
          background-color: rgb(15 23 42 / 0.7);
          color: rgb(241 245 249);
          padding: 0.5rem 0.75rem;
          font-size: 0.875rem;
          outline: none;
          transition: border 0.15s;
        }
        .input:focus {
          border-color: rgb(34 211 238 / 0.6);
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
