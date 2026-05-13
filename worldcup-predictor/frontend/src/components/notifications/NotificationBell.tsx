'use client';

import { Bell } from 'lucide-react';
import { useEffect, useState } from 'react';

import { NotificationDrawer } from './NotificationDrawer';
import { useAuth } from '@/hooks/useAuth';
import { useSubscription } from '@/hooks/useSubscription';
import { useT } from '@/i18n/I18nProvider';
import { getUnreadCount } from '@/lib/notificationsApi';
import { cn } from '@/lib/utils';

const POLL_INTERVAL_MS = 30_000;

export function NotificationBell({ className }: { className?: string }) {
  const { isAuthenticated } = useAuth();
  const { tier } = useSubscription();
  const t = useT();
  const [unreadCount, setUnreadCount] = useState(0);
  const [open, setOpen] = useState(false);

  // The notification centre is a basic+ feature — free users still see
  // existing push-preferences but the bell is hidden.
  const enabled = isAuthenticated && tier !== 'free';

  useEffect(() => {
    if (!enabled) {
      setUnreadCount(0);
      return;
    }
    let cancelled = false;
    const tick = async () => {
      try {
        const { unreadCount: count } = await getUnreadCount();
        if (!cancelled) setUnreadCount(count);
      } catch {
        // Network blip — keep the previous count, retry next tick.
      }
    };
    void tick();
    const id = window.setInterval(() => void tick(), POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [enabled]);

  if (!enabled) {
    return null;
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label={t('notificationCentre.bellLabel')}
        className={cn(
          'relative flex h-9 w-9 items-center justify-center rounded-full border border-slate-700 bg-slate-800/70 text-slate-300 transition-colors hover:border-brand-500/40 hover:bg-slate-700 hover:text-brand-400',
          className,
        )}
      >
        <Bell size={18} />
        {unreadCount > 0 ? (
          <span
            className="absolute -right-0.5 -top-0.5 inline-flex h-4 min-w-[16px] items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-bold text-white"
            aria-label={t('notificationCentre.unreadLabel')}
          >
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        ) : null}
      </button>
      <NotificationDrawer
        open={open}
        onClose={() => setOpen(false)}
        onUnreadChange={setUnreadCount}
      />
    </>
  );
}
