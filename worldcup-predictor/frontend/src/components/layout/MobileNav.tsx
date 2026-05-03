'use client';

import { Calendar, ListChecks, Trophy, User } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

import { cn } from '@/lib/utils';

const ITEMS = [
  { href: '/', label: '今日', icon: Calendar },
  { href: '/track-record', label: '战绩', icon: ListChecks },
  { href: '/worldcup/bracket', label: '淘汰赛', icon: Trophy },
  { href: '/profile', label: '我的', icon: User },
] as const;

export function MobileNav() {
  const pathname = usePathname();
  return (
    <nav
      aria-label="主导航"
      className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-4 border-t border-slate-200 bg-white md:hidden"
    >
      {ITEMS.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || (href !== '/' && pathname.startsWith(href));
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              'flex flex-col items-center justify-center gap-1 py-2 text-xs',
              active ? 'text-brand-600' : 'text-slate-500',
            )}
          >
            <Icon size={20} />
            <span>{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
