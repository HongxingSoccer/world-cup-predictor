'use client';

import { Calendar, ListChecks, Trophy, User } from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

import { useT } from '@/i18n/I18nProvider';
import { cn } from '@/lib/utils';

const ITEMS = [
  { href: '/', key: 'nav.todayShort', icon: Calendar },
  { href: '/track-record', key: 'nav.trackRecord', icon: ListChecks },
  { href: '/worldcup/bracket', key: 'nav.knockout', icon: Trophy },
  { href: '/profile', key: 'nav.myMatches', icon: User },
] as const;

export function MobileNav() {
  const t = useT();
  const pathname = usePathname();
  return (
    <nav
      aria-label={t('nav.mainNav')}
      className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-4 border-t border-slate-800/70 bg-ink-900/85 backdrop-blur-xl supports-[backdrop-filter]:bg-ink-900/70 md:hidden"
    >
      {ITEMS.map(({ href, key, icon: Icon }) => {
        const active = pathname === href || (href !== '/' && pathname.startsWith(href));
        return (
          <Link
            key={href}
            href={href}
            className={cn(
              'flex flex-col items-center justify-center gap-1 py-2 text-xs transition-colors',
              active ? 'text-brand-400' : 'text-slate-400 hover:text-slate-200',
            )}
          >
            <Icon size={20} />
            <span>{t(key)}</span>
          </Link>
        );
      })}
    </nav>
  );
}
