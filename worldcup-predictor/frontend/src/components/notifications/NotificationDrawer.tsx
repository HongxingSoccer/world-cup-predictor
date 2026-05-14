'use client';

import { X } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/Button';
import { useT } from '@/i18n/I18nProvider';
import { listNotifications, markAllRead, markRead } from '@/lib/notificationsApi';
import { cn } from '@/lib/utils';
import type { NotificationResponse } from '@/types/positions';

interface Props {
  open: boolean;
  onClose: () => void;
  onUnreadChange: (count: number) => void;
}

const KIND_STYLE: Record<string, string> = {
  hedge_window: 'border-amber-500/40 bg-amber-500/10',
  position_settled: 'border-cyan-500/40 bg-cyan-500/10',
  arbitrage: 'border-emerald-500/40 bg-emerald-500/10',
  high_ev: 'border-violet-500/40 bg-violet-500/10',
};

export function NotificationDrawer({ open, onClose, onUnreadChange }: Props) {
  const t = useT();
  const [items, setItems] = useState<NotificationResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setItems(null);
    setError(null);
    (async () => {
      try {
        const data = await listNotifications(50);
        if (cancelled) return;
        setItems(data.items);
        onUnreadChange(data.unreadCount);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : t('notificationCentre.loadFailed'));
        setItems([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, onUnreadChange, t]);

  useEffect(() => {
    if (!open) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  const onMarkOne = async (id: number) => {
    try {
      const updated = await markRead(id);
      setItems((prev) =>
        prev ? prev.map((n) => (n.id === id ? updated : n)) : prev,
      );
      const unread = (items ?? []).filter((n) => n.id !== id && !n.readAt).length;
      onUnreadChange(unread);
    } catch {
      // Silent: user can try again.
    }
  };

  const onMarkAll = async () => {
    setPending(true);
    try {
      await markAllRead();
      const now = new Date().toISOString();
      setItems((prev) => prev?.map((n) => (n.readAt ? n : { ...n, readAt: now })) ?? null);
      onUnreadChange(0);
    } catch {
      setError(t('notificationCentre.markAllFailed'));
    } finally {
      setPending(false);
    }
  };

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t('notificationCentre.title')}
      className="fixed inset-0 z-50"
    >
      <button
        type="button"
        aria-label={t('common.close')}
        className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="absolute right-0 top-0 flex h-full w-full max-w-md flex-col bg-slate-950/95 shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-800/70 px-4 py-3">
          <h2 className="text-base font-semibold text-slate-100">{t('notificationCentre.title')}</h2>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={onMarkAll}
              disabled={pending}
              className="!h-7 !px-2 !text-xs"
            >
              {t('notificationCentre.markAllRead')}
            </Button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-full p-1 text-slate-400 hover:bg-slate-800/70"
              aria-label={t('common.close')}
            >
              <X size={18} />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-3">
          {error ? <p className="mb-2 text-xs text-rose-400">{error}</p> : null}
          {items === null ? (
            <div className="space-y-2">
              <div className="h-16 animate-pulse rounded-xl bg-slate-800/60" />
              <div className="h-16 animate-pulse rounded-xl bg-slate-800/60" />
            </div>
          ) : items.length === 0 ? (
            <p className="py-12 text-center text-sm text-slate-400">{t('notificationCentre.empty')}</p>
          ) : (
            <ul className="space-y-2">
              {items.map((n) => (
                <li key={n.id}>
                  <NotificationCard notification={n} onClick={() => onMarkOne(n.id)} />
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function NotificationCard({
  notification,
  onClick,
}: {
  notification: NotificationResponse;
  onClick: () => void;
}) {
  const t = useT();
  const isUnread = !notification.readAt;
  const kindClass = KIND_STYLE[notification.kind] ?? 'border-slate-700 bg-slate-900/60';

  const handleClick = () => {
    if (isUnread) onClick();
    if (notification.targetUrl && typeof window !== 'undefined') {
      window.location.href = notification.targetUrl;
    }
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      className={cn(
        'block w-full rounded-xl border px-4 py-3 text-left transition-colors',
        kindClass,
        isUnread ? 'ring-1 ring-cyan-500/30' : 'opacity-75',
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-semibold text-slate-100">{notification.title}</span>
        <span className="shrink-0 text-[10px] uppercase tracking-wide text-slate-400">
          {t(`notificationCentre.kind.${notification.kind}`) || notification.kind}
        </span>
      </div>
      <p className="mt-1 text-xs text-slate-300">{notification.body}</p>
      <p className="mt-2 text-[10px] text-slate-500">
        {new Date(notification.createdAt).toLocaleString()}
      </p>
    </button>
  );
}
