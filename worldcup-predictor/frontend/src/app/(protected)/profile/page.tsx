'use client';

import { Bell, Pencil } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useEffect, useState, useTransition } from 'react';

import { MyFavoritesCard } from '@/components/match/MyFavoritesCard';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { useAuth } from '@/hooks/useAuth';
import { useSubscription } from '@/hooks/useSubscription';
import { api, apiPost } from '@/lib/api';
import { useAuthStore } from '@/stores/auth-store';
import type { UserResponse } from '@/types';

export default function ProfilePage() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuth();
  const { tier, expiresAt } = useSubscription();
  const logout = useAuthStore((s) => s.logout);
  const hydrateFromMe = useAuthStore((s) => s.hydrateFromMe);

  useEffect(() => {
    // SSR-safe: only redirect on the client.
    if (typeof window !== 'undefined' && !isAuthenticated) {
      router.replace('/login');
    }
  }, [isAuthenticated, router]);

  if (!user) {
    return null;
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div>
            <h1 className="text-base font-semibold text-slate-100">个人中心</h1>
            <p className="mt-0.5 text-xs text-slate-400">
              {user.nickname ?? user.email ?? user.phone}
            </p>
          </div>
          <Badge tone={tier === 'free' ? 'neutral' : 'success'}>{tier.toUpperCase()}</Badge>
        </CardHeader>
        <CardBody className="space-y-2 text-sm text-slate-300">
          <NicknameRow user={user} onUpdated={hydrateFromMe} />
          <Row label="UUID" value={user.uuid} />
          <Row label="手机号" value={user.phone ?? '—'} />
          <Row label="邮箱" value={user.email ?? '—'} />
          <Row label="语言" value={user.locale} />
          <Row label="时区" value={user.timezone} />
        </CardBody>
      </Card>

      <SubscriptionCard
        tier={tier}
        expiresAt={expiresAt}
        onUpgrade={() => router.push('/subscribe')}
      />

      <MyFavoritesCard />

      <Card>
        <CardBody>
          <button
            type="button"
            onClick={() => router.push('/notifications')}
            className="flex w-full items-center gap-3 text-left"
          >
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-cyan-500/15 text-cyan-300">
              <Bell size={18} />
            </span>
            <div className="flex-1">
              <div className="text-sm font-semibold text-slate-100">通知偏好</div>
              <div className="text-xs text-slate-400">
                价值信号 · 红单战报 · 比赛开球 · 免打扰时段
              </div>
            </div>
            <span className="text-slate-400">›</span>
          </button>
        </CardBody>
      </Card>

      <div className="flex justify-end">
        <Button
          variant="ghost"
          onClick={async () => {
            await logout();
            router.push('/');
          }}
        >
          退出登录
        </Button>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between border-b border-slate-800/70 py-1.5 last:border-0">
      <span className="text-slate-400">{label}</span>
      <span className="font-medium text-slate-100">{value}</span>
    </div>
  );
}

interface NicknameRowProps {
  user: UserResponse;
  onUpdated: (user: UserResponse) => void;
}

function NicknameRow({ user, onUpdated }: NicknameRowProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(user.nickname ?? '');
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const save = () => {
    const trimmed = draft.trim();
    if (!trimmed) {
      setError('昵称不能为空');
      return;
    }
    if (trimmed === user.nickname) {
      setEditing(false);
      return;
    }
    setError(null);
    startTransition(async () => {
      try {
        const updated = await api
          .put<UserResponse>('/api/v1/users/me', { nickname: trimmed })
          .then((r) => r.data);
        onUpdated(updated);
        setEditing(false);
      } catch {
        setError('更新失败，请稍后重试');
      }
    });
  };

  if (editing) {
    return (
      <div className="flex flex-col gap-2 border-b border-slate-800/70 py-2">
        <div className="flex items-center justify-between gap-2">
          <span className="text-slate-400">昵称</span>
          <input
            type="text"
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            disabled={pending}
            maxLength={32}
            className="flex-1 rounded-md border border-slate-700 bg-slate-900/70 px-2 py-1 text-right text-sm text-slate-100 outline-none focus:border-cyan-400/60"
            onKeyDown={(e) => {
              if (e.key === 'Enter') save();
              if (e.key === 'Escape') setEditing(false);
            }}
          />
        </div>
        <div className="flex justify-end gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setEditing(false);
              setDraft(user.nickname ?? '');
            }}
            disabled={pending}
          >
            取消
          </Button>
          <Button variant="primary" size="sm" onClick={save} disabled={pending}>
            {pending ? '保存中…' : '保存'}
          </Button>
        </div>
        {error ? <div className="text-xs text-rose-400">{error}</div> : null}
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between border-b border-slate-800/70 py-1.5">
      <span className="text-slate-400">昵称</span>
      <button
        type="button"
        onClick={() => {
          setDraft(user.nickname ?? '');
          setEditing(true);
        }}
        className="group inline-flex items-center gap-1.5 font-medium text-slate-100 hover:text-cyan-300"
        aria-label="修改昵称"
      >
        <span>{user.nickname ?? '未设置'}</span>
        <Pencil
          size={12}
          className="text-slate-500 transition-colors group-hover:text-cyan-300"
        />
      </button>
    </div>
  );
}

interface SubscriptionCardProps {
  tier: string;
  expiresAt?: string | null;
  onUpgrade: () => void;
}

function SubscriptionCard({ tier, expiresAt, onUpgrade }: SubscriptionCardProps) {
  const [pending, startTransition] = useTransition();
  const [cancelled, setCancelled] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isPaid = tier !== 'free';

  const cancel = () => {
    if (!confirm('确定取消自动续费？当前订阅期内仍可使用，到期后自动降级。')) {
      return;
    }
    setError(null);
    startTransition(async () => {
      try {
        await apiPost('/api/v1/subscriptions/cancel', {});
        setCancelled(true);
      } catch {
        setError('取消失败，请稍后重试');
      }
    });
  };

  return (
    <Card>
      <CardHeader>
        <h2 className="text-base font-semibold text-slate-100">订阅状态</h2>
      </CardHeader>
      <CardBody className="space-y-2 text-sm text-slate-300">
        <Row label="当前等级" value={tier.toUpperCase()} />
        <Row
          label="到期时间"
          value={expiresAt ? new Date(expiresAt).toLocaleDateString('zh-CN') : '—'}
        />
        {cancelled ? (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
            已取消自动续费，当前订阅期到期后自动降级到 FREE。
          </div>
        ) : null}
        {error ? <div className="text-xs text-rose-400">{error}</div> : null}
        <div className="flex flex-wrap gap-2 pt-2">
          <Button variant="primary" onClick={onUpgrade}>
            升级 / 续费
          </Button>
          {isPaid && !cancelled ? (
            <Button variant="ghost" onClick={cancel} disabled={pending}>
              {pending ? '处理中…' : '取消自动续费'}
            </Button>
          ) : null}
        </div>
      </CardBody>
    </Card>
  );
}
