'use client';

import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { useAuth } from '@/hooks/useAuth';
import { useSubscription } from '@/hooks/useSubscription';
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
            <h1 className="text-base font-semibold text-slate-900">个人中心</h1>
            <p className="mt-0.5 text-xs text-slate-500">{user.nickname ?? user.email ?? user.phone}</p>
          </div>
          <Badge tone={tier === 'free' ? 'neutral' : 'success'}>{tier.toUpperCase()}</Badge>
        </CardHeader>
        <CardBody className="space-y-2 text-sm text-slate-700">
          <Row label="UUID" value={user.uuid} />
          <Row label="手机号" value={user.phone ?? '—'} />
          <Row label="邮箱" value={user.email ?? '—'} />
          <Row label="语言" value={user.locale} />
          <Row label="时区" value={user.timezone} />
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <h2 className="text-base font-semibold text-slate-900">订阅状态</h2>
        </CardHeader>
        <CardBody className="space-y-2 text-sm text-slate-700">
          <Row label="当前等级" value={tier.toUpperCase()} />
          <Row label="到期时间" value={expiresAt ? new Date(expiresAt).toLocaleDateString('zh-CN') : '—'} />
          <div className="flex gap-2 pt-2">
            <Button variant="primary" onClick={() => router.push('/subscribe')}>
              升级 / 续费
            </Button>
          </div>
        </CardBody>
      </Card>

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
    <div className="flex items-center justify-between border-b border-slate-100 py-1.5 last:border-0">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium text-slate-900">{value}</span>
    </div>
  );
}
