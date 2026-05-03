'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

import { LocaleSwitcher } from '@/components/i18n/LocaleSwitcher';
import { useT } from '@/i18n/I18nProvider';

const NAV_ITEMS: { href: string; key: string }[] = [
  { href: '/admin', key: 'admin.nav.overview' },
  { href: '/admin/users', key: 'admin.nav.users' },
  { href: '/admin/subscriptions', key: 'admin.nav.subscriptions' },
  { href: '/admin/predictions', key: 'admin.nav.predictions' },
  { href: '/admin/reports', key: 'admin.nav.reports' },
  { href: '/admin/data-sources', key: 'admin.nav.dataSources' },
  { href: '/admin/push', key: 'admin.nav.push' },
  { href: '/admin/content', key: 'admin.nav.content' },
  { href: '/admin/system', key: 'admin.nav.system' },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const t = useT();
  const pathname = usePathname();

  return (
    <div className="grid grid-cols-12 gap-4">
      <aside className="col-span-12 md:col-span-3">
        <div className="rounded-md border border-slate-200 bg-white p-3">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-700">Admin</h2>
            <LocaleSwitcher />
          </div>
          <nav className="flex flex-col gap-1 text-sm">
            {NAV_ITEMS.map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href as never}
                  className={`rounded-md px-2 py-1.5 ${
                    active
                      ? 'bg-emerald-50 font-medium text-emerald-700'
                      : 'text-slate-600 hover:bg-slate-50'
                  }`}
                >
                  {t(item.key)}
                </Link>
              );
            })}
          </nav>
        </div>
      </aside>
      <section className="col-span-12 md:col-span-9">{children}</section>
    </div>
  );
}
