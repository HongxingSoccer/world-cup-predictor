'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useState, useTransition } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { useAuth } from '@/hooks/useAuth';
import { useSubscription } from '@/hooks/useSubscription';
import { apiPost } from '@/lib/api';
import { useAuthStore } from '@/stores/auth-store';

export default function ProfilePage() {
  const router = useRouter();
  const { user, isAuthenticated } = useAuth();
  const { tier, expiresAt } = useSubscription();
  const logout = useAuthStore((s) => s.logout);

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
            <p className="mt-0.5 text-xs text-slate-400">{user.nickname ?? user.email ?? user.phone}</p>
          </div>
          <Badge tone={tier === 'free' ? 'neutral' : 'success'}>{tier.toUpperCase()}</Badge>
        </CardHeader>
        <CardBody className="space-y-2 text-sm text-slate-300">
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

      <div className="flex justify-end">
        <Button variant="ghost" onClick={async () => { await logout(); router.push('/'); }}>
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

interface SubscriptionCardProps {
  tier: string;
  expiresAt?: string | null;
  onUpgrade: () => void;
}

function SubscriptionCard({ tier, expiresAt, onUpgrade }: SubscriptionCardProps) {
  const [pending, startTransition] = useTransition();
  // Local optimistic flag — reflects auto-renew off after a successful POST.
  // The page rebuilds on next visit; we only need to hide the button + show
  // the confirmation in this session.
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
