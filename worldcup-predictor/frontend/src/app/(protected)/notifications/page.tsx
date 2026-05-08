'use client';

import { Bell, Star, Trophy, Zap } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useEffect, useState, useTransition } from 'react';

import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { useT } from '@/i18n/I18nProvider';
import { useAuth } from '@/hooks/useAuth';
import { apiGet, api } from '@/lib/api';
import { cn } from '@/lib/utils';

interface PushSettings {
  enableHighEv: boolean;
  enableReports: boolean;
  enableMatchStart: boolean;
  enableRedHit: boolean;
  quietHoursStart: string | null;
  quietHoursEnd: string | null;
}

interface PushSettingsRaw {
  enableHighEv?: boolean;
  enable_high_ev?: boolean;
  enableReports?: boolean;
  enable_reports?: boolean;
  enableMatchStart?: boolean;
  enable_match_start?: boolean;
  enableRedHit?: boolean;
  enable_red_hit?: boolean;
  quietHoursStart?: string | null;
  quiet_hours_start?: string | null;
  quietHoursEnd?: string | null;
  quiet_hours_end?: string | null;
}

const DEFAULTS: PushSettings = {
  enableHighEv: true,
  enableReports: true,
  enableMatchStart: true,
  enableRedHit: true,
  quietHoursStart: null,
  quietHoursEnd: null,
};

function fromRaw(raw: PushSettingsRaw): PushSettings {
  return {
    enableHighEv: pickBool(raw.enableHighEv, raw.enable_high_ev, true),
    enableReports: pickBool(raw.enableReports, raw.enable_reports, true),
    enableMatchStart: pickBool(raw.enableMatchStart, raw.enable_match_start, true),
    enableRedHit: pickBool(raw.enableRedHit, raw.enable_red_hit, true),
    quietHoursStart: (raw.quietHoursStart ?? raw.quiet_hours_start ?? null) || null,
    quietHoursEnd: (raw.quietHoursEnd ?? raw.quiet_hours_end ?? null) || null,
  };
}

function pickBool(camel: boolean | undefined, snake: boolean | undefined, fallback: boolean): boolean {
  if (typeof camel === 'boolean') return camel;
  if (typeof snake === 'boolean') return snake;
  return fallback;
}

interface ChannelDef {
  key: keyof Pick<PushSettings, 'enableHighEv' | 'enableReports' | 'enableMatchStart' | 'enableRedHit'>;
  labelKey: string;
  detailKey: string;
  icon: LucideIcon;
}

const CHANNELS: ChannelDef[] = [
  {
    key: 'enableHighEv',
    labelKey: 'notifications.channelHighEv',
    detailKey: 'notifications.channelHighEvDetail',
    icon: Star,
  },
  {
    key: 'enableMatchStart',
    labelKey: 'notifications.channelMatchStart',
    detailKey: 'notifications.channelMatchStartDetail',
    icon: Trophy,
  },
  {
    key: 'enableRedHit',
    labelKey: 'notifications.channelRedHit',
    detailKey: 'notifications.channelRedHitDetail',
    icon: Zap,
  },
  {
    key: 'enableReports',
    labelKey: 'notifications.channelAiReport',
    detailKey: 'notifications.channelAiReportDetail',
    icon: Bell,
  },
];

export default function NotificationsPage() {
  const t = useT();
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const [settings, setSettings] = useState<PushSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    if (typeof window !== 'undefined' && !isAuthenticated) {
      router.replace('/login?next=/notifications');
    }
  }, [isAuthenticated, router]);

  useEffect(() => {
    if (!isAuthenticated) return;
    let cancelled = false;
    (async () => {
      try {
        const raw = await apiGet<PushSettingsRaw>('/api/v1/push/settings');
        if (cancelled) return;
        setSettings(fromRaw(raw));
      } catch {
        if (cancelled) return;
        setSettings(DEFAULTS);
        setError(t('notifications.loadFallback'));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, t]);

  if (!settings) {
    return (
      <div className="space-y-3">
        <h1 className="text-xl font-bold text-slate-100">{t('notifications.title')}</h1>
        <Card>
          <CardBody>
            <div className="space-y-2">
              <div className="h-12 animate-pulse rounded-xl bg-slate-800/60" />
              <div className="h-12 animate-pulse rounded-xl bg-slate-800/60" />
              <div className="h-12 animate-pulse rounded-xl bg-slate-800/60" />
            </div>
          </CardBody>
        </Card>
      </div>
    );
  }

  const setBool = (key: ChannelDef['key'], value: boolean) =>
    setSettings({ ...settings, [key]: value });

  const setQuiet = (
    field: 'quietHoursStart' | 'quietHoursEnd',
    value: string,
  ) => setSettings({ ...settings, [field]: value || null });

  const save = () => {
    setError(null);
    startTransition(async () => {
      try {
        await api.put('/api/v1/push/settings', {
          enable_high_ev: settings.enableHighEv,
          enable_reports: settings.enableReports,
          enable_match_start: settings.enableMatchStart,
          enable_red_hit: settings.enableRedHit,
          quiet_hours_start: settings.quietHoursStart,
          quiet_hours_end: settings.quietHoursEnd,
        });
        setSavedAt(Date.now());
      } catch {
        setError(t('notifications.saveFailed'));
      }
    });
  };

  const allOff = CHANNELS.every((c) => !settings[c.key]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-slate-100">{t('notifications.title')}</h1>
        <p className="mt-1 text-xs text-slate-400">{t('notifications.subtitle')}</p>
      </div>

      <Card>
        <CardHeader>
          <h2 className="text-sm font-semibold text-slate-100">{t('notifications.channels')}</h2>
          {allOff ? (
            <span className="text-xs text-amber-300">{t('notifications.allDisabled')}</span>
          ) : null}
        </CardHeader>
        <CardBody className="space-y-1">
          {CHANNELS.map(({ key, labelKey, detailKey, icon: Icon }) => (
            <ToggleRow
              key={key}
              icon={Icon}
              label={t(labelKey)}
              detail={t(detailKey)}
              checked={settings[key]}
              onChange={(v) => setBool(key, v)}
            />
          ))}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <h2 className="text-sm font-semibold text-slate-100">{t('notifications.quietHours')}</h2>
          <span className="text-xs text-slate-400">{t('notifications.quietSubtitle')}</span>
        </CardHeader>
        <CardBody className="grid grid-cols-2 gap-3">
          <TimeInput
            label={t('notifications.quietStart')}
            value={settings.quietHoursStart ?? ''}
            onChange={(v) => setQuiet('quietHoursStart', v)}
          />
          <TimeInput
            label={t('notifications.quietEnd')}
            value={settings.quietHoursEnd ?? ''}
            onChange={(v) => setQuiet('quietHoursEnd', v)}
          />
        </CardBody>
      </Card>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-xs">
          {savedAt ? (
            <span className="text-emerald-300">{t('notifications.savedOk')}</span>
          ) : error ? (
            <span className="text-rose-400">{error}</span>
          ) : (
            <span className="text-slate-500">{t('notifications.notSaved')}</span>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <TestPushButton />
          <Button onClick={save} disabled={pending}>
            {pending ? t('common.saving') : t('common.save')}
          </Button>
        </div>
      </div>
    </div>
  );
}

function TestPushButton() {
  const t = useT();
  const [state, setState] = useState<'idle' | 'pending' | 'sent' | 'error'>('idle');
  const click = async () => {
    setState('pending');
    try {
      await api.post('/api/v1/push/settings/test', {
        channel: 'wechat',
        title: 'WCP test',
        body: 'This is a test notification.',
      });
      setState('sent');
      setTimeout(() => setState('idle'), 3000);
    } catch {
      setState('error');
      setTimeout(() => setState('idle'), 3000);
    }
  };
  return (
    <Button variant="ghost" onClick={click} disabled={state === 'pending'}>
      {state === 'pending'
        ? t('notifications.testPushSending')
        : state === 'sent'
          ? t('notifications.testPushSent')
          : state === 'error'
            ? t('notifications.testPushFailed')
            : t('notifications.testPush')}
    </Button>
  );
}

function ToggleRow({
  icon: Icon,
  label,
  detail,
  checked,
  onChange,
}: {
  icon: LucideIcon;
  label: string;
  detail: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={cn(
        'flex w-full items-center gap-3 rounded-xl border px-3 py-3 text-left transition-colors',
        checked
          ? 'border-cyan-500/30 bg-cyan-500/5 hover:bg-cyan-500/10'
          : 'border-slate-800/70 bg-slate-900/30 hover:bg-slate-800/50',
      )}
    >
      <span
        className={cn(
          'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg',
          checked ? 'bg-cyan-500/15 text-cyan-300' : 'bg-slate-800/80 text-slate-400',
        )}
      >
        <Icon size={18} />
      </span>
      <div className="flex-1">
        <div className="text-sm font-semibold text-slate-100">{label}</div>
        <div className="text-xs text-slate-400">{detail}</div>
      </div>
      <Switch checked={checked} />
    </button>
  );
}

function Switch({ checked }: { checked: boolean }) {
  return (
    <span
      aria-hidden
      className={cn(
        'relative inline-block h-5 w-9 shrink-0 rounded-full transition-colors',
        checked ? 'bg-cyan-500' : 'bg-slate-700',
      )}
    >
      <span
        className={cn(
          'absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform',
          checked ? 'translate-x-[18px]' : 'translate-x-0.5',
        )}
      />
    </span>
  );
}

function TimeInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs text-slate-400">{label}</span>
      <input
        type="time"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-md border border-slate-700 bg-slate-900/70 px-2 py-1.5 text-sm tabular-nums text-slate-100 outline-none focus:border-cyan-400/60"
      />
    </label>
  );
}
