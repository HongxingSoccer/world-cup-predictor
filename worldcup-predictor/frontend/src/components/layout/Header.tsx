'use client';

import Link from 'next/link';
import { Trophy, User as UserIcon } from 'lucide-react';

import { CompactLocaleToggle } from '@/components/i18n/CompactLocaleToggle';
import { useAuth } from '@/hooks/useAuth';
import { useSubscription } from '@/hooks/useSubscription';
import { cn } from '@/lib/utils';

export function Header() {
  const { user, isAuthenticated } = useAuth();
  const { tier } = useSubscription();

  return (
    <header className="sticky top-0 z-30 border-b border-slate-800/70 bg-ink-900/70 backdrop-blur-xl supports-[backdrop-filter]:bg-ink-900/60">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <Link href="/" className="flex items-center gap-2 text-slate-100">
          <Trophy size={20} className="text-brand-400" />
          <span className="font-bold tracking-tight">WCP · 世界杯预测</span>
        </Link>

        <nav className="hidden items-center gap-6 text-sm md:flex">
          <Link href="/" className="text-slate-300 transition-colors hover:text-brand-400">
            今日比赛
          </Link>
          <Link href="/track-record" className="text-slate-300 transition-colors hover:text-brand-400">
            战绩
          </Link>
          <Link href="/worldcup/groups" className="text-slate-300 transition-colors hover:text-brand-400">
            小组赛
          </Link>
          <Link href="/worldcup/bracket" className="text-slate-300 transition-colors hover:text-brand-400">
            淘汰赛
          </Link>
          <Link href="/worldcup/simulation" className="text-slate-300 transition-colors hover:text-brand-400">
            夺冠概率
          </Link>
          <Link href="/subscribe" className="text-slate-300 transition-colors hover:text-brand-400">
            订阅
          </Link>
        </nav>

        <div className="flex items-center gap-2">
          <CompactLocaleToggle />
          {isAuthenticated && tier !== 'free' ? (
            <span
              className={cn(
                'hidden rounded-full border px-2.5 py-1 text-xs font-semibold sm:inline-block',
                tier === 'premium'
                  ? 'border-accent-500/40 bg-accent-500/15 text-accent-400'
                  : 'border-brand-500/40 bg-brand-500/15 text-brand-400',
              )}
            >
              {tier === 'premium' ? 'Premium' : 'Basic'}
            </span>
          ) : null}
          <Link
            href={isAuthenticated ? '/profile' : '/login'}
            className="flex h-9 w-9 items-center justify-center rounded-full border border-slate-700 bg-slate-800/70 text-slate-300 transition-colors hover:border-brand-500/40 hover:bg-slate-700 hover:text-brand-400"
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
