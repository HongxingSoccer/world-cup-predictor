'use client';

import Link from 'next/link';
import { Trophy, User as UserIcon } from 'lucide-react';

import { useAuth } from '@/hooks/useAuth';
import { useSubscription } from '@/hooks/useSubscription';
import { cn } from '@/lib/utils';

export function Header() {
  const { user, isAuthenticated } = useAuth();
  const { tier } = useSubscription();

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/80 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <Link href="/" className="flex items-center gap-2 text-slate-900">
          <Trophy size={20} className="text-brand-600" />
          <span className="font-bold">WCP · 世界杯预测</span>
        </Link>

        <nav className="hidden items-center gap-6 text-sm md:flex">
          <Link href="/" className="text-slate-600 hover:text-slate-900">
            今日比赛
          </Link>
          <Link href="/track-record" className="text-slate-600 hover:text-slate-900">
            战绩
          </Link>
          <Link href="/worldcup/groups" className="text-slate-600 hover:text-slate-900">
            小组赛
          </Link>
          <Link href="/worldcup/bracket" className="text-slate-600 hover:text-slate-900">
            淘汰赛
          </Link>
          <Link href="/subscribe" className="text-slate-600 hover:text-slate-900">
            订阅
          </Link>
        </nav>

        <div className="flex items-center gap-2">
          {isAuthenticated && tier !== 'free' ? (
            <span
              className={cn(
                'hidden rounded-full px-2.5 py-1 text-xs font-semibold sm:inline-block',
                tier === 'premium'
                  ? 'bg-amber-100 text-amber-800'
                  : 'bg-emerald-100 text-emerald-800',
              )}
            >
              {tier === 'premium' ? 'Premium' : 'Basic'}
            </span>
          ) : null}
          <Link
            href={isAuthenticated ? '/profile' : '/login'}
            className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 text-slate-700 hover:bg-slate-200"
            aria-label={isAuthenticated ? '个人中心' : '登录'}
          >
            <UserIcon size={18} />
            {user?.nickname ? <span className="sr-only">{user.nickname}</span> : null}
          </Link>
        </div>
      </div>
    </header>
  );
}
