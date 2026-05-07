'use client';

import { Bell, Star, Trophy, Zap } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useEffect, useState, useTransition } from 'react';

import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
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
  label: string;
  detail: string;
  icon: LucideIcon;
}

const CHANNELS: ChannelDef[] = [
  {
    key: 'enableHighEv',
    label: '价值信号 (高 EV)',
    detail: '⭐⭐ 及以上的赔率价值机会即时推送',
    icon: Star,
  },
  {
    key: 'enableMatchStart',
    label: '比赛开球提醒',
    detail: '关注的比赛开球前 15 分钟通知',
    icon: Trophy,
  },
  {
    key: 'enableRedHit',
    label: '红单战报',
    detail: '当 AI 预测命中时第一时间通知',
    icon: Zap,
  },
  {
    key: 'enableReports',
    label: 'AI 比赛分析报告',
    detail: '重点比赛的赛前 AI 深度分析发布时',
    icon: Bell,
  },
];

export default function NotificationsPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const [settings, setSettings] = useState<PushSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    if (typeof window !== 'undefined' && !isAuthenticated) {
      router.replace('/login');
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
        setError('未能加载已有偏好，已套用默认值');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated]);

  if (!settings) {
    return (
      <div className="space-y-3">
        <h1 className="text-xl font-bold text-slate-100">通知偏好</h1>
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
        setError('保存失败，请稍后重试');
      }
    });
  };

  const allOff = CHANNELS.every((c) => !settings[c.key]);

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-slate-100">通知偏好</h1>
        <p className="mt-1 text-xs text-slate-400">
          决定哪些事件给你发推送 — 关掉不感兴趣的频道，免静默时间避免夜里被吵醒。
        </p>
      </div>

      <Card>
        <CardHeader>
          <h2 className="text-sm font-semibold text-slate-100">推送频道</h2>
          {allOff ? (
            <span className="text-xs text-amber-300">所有通知已关闭</span>
          ) : null}
        </CardHeader>
        <CardBody className="space-y-1">
          {CHANNELS.map(({ key, label, detail, icon: Icon }) => (
            <ToggleRow
              key={key}
              icon={Icon}
              label={label}
              detail={detail}
              checked={settings[key]}
              onChange={(v) => setBool(key, v)}
            />
          ))}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <h2 className="text-sm font-semibold text-slate-100">免打扰时段</h2>
          <span className="text-xs text-slate-400">UTC 时区，留空表示全天可推送</span>
        </CardHeader>
        <CardBody className="grid grid-cols-2 gap-3">
          <TimeInput
            label="开始"
            value={settings.quietHoursStart ?? ''}
            onChange={(v) => setQuiet('quietHoursStart', v)}
          />
          <TimeInput
            label="结束"
            value={settings.quietHoursEnd ?? ''}
            onChange={(v) => setQuiet('quietHoursEnd', v)}
          />
        </CardBody>
      </Card>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-xs">
          {savedAt ? (
            <span className="text-emerald-300">✓ 已保存</span>
          ) : error ? (
            <span className="text-rose-400">{error}</span>
          ) : (
            <span className="text-slate-500">未保存</span>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <TestPushButton />
          <Button onClick={save} disabled={pending}>
            {pending ? '保存中…' : '保存'}
          </Button>
        </div>
      </div>
    </div>
  );
}

function TestPushButton() {
  const [state, setState] = useState<'idle' | 'pending' | 'sent' | 'error'>('idle');
  const click = async () => {
    setState('pending');
    try {
      await api.post('/api/v1/push/settings/test', {
        channel: 'wechat',
        title: 'WCP 测试推送',
        body: '这是一条测试通知，用以验证你的推送偏好已正确保存。',
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
        ? '发送中…'
        : state === 'sent'
          ? '✓ 已发送（演练）'
          : state === 'error'
            ? '发送失败'
            : '发条测试推送'}
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
