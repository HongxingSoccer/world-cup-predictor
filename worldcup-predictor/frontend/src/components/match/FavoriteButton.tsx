'use client';

import { Heart } from 'lucide-react';
import Link from 'next/link';
import { useState, useTransition } from 'react';

import { Button } from '@/components/ui/Button';
import { useAuth } from '@/hooks/useAuth';
import { apiPost } from '@/lib/api';
import { cn } from '@/lib/utils';

interface FavoriteButtonProps {
  matchId: number;
  /** Server-rendered initial state. Undefined / null → anonymous (renders login CTA). */
  initialFavorited: boolean | null | undefined;
}

interface ToggleResponse {
  matchId: number;
  favorite: boolean;
}

/**
 * Heart-icon toggle for favouriting a match. Anonymous users see a "登录后收藏"
 * Link to /login; authenticated users get the optimistic toggle.
 */
export function FavoriteButton({ matchId, initialFavorited }: FavoriteButtonProps) {
  const { isAuthenticated } = useAuth();
  const [favorited, setFavorited] = useState<boolean>(Boolean(initialFavorited));
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  if (!isAuthenticated || initialFavorited === null || initialFavorited === undefined) {
    return (
      <Link href="/login">
        <Button variant="ghost" size="sm" leftIcon={<Heart size={16} />}>
          登录后收藏
        </Button>
      </Link>
    );
  }

  const onClick = () => {
    setError(null);
    // Optimistic flip — if the API call fails, revert.
    const next = !favorited;
    setFavorited(next);
    startTransition(async () => {
      try {
        const result = await apiPost<ToggleResponse, Record<string, never>>(
          `/api/v1/matches/${matchId}/favorite`,
          {},
        );
        setFavorited(result.favorite);
      } catch {
        setFavorited(!next);
        setError('收藏失败，请稍后重试');
      }
    });
  };

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={onClick}
        disabled={pending}
        aria-pressed={favorited}
        aria-label={favorited ? '取消收藏' : '收藏比赛'}
        className={cn(
          'inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-semibold transition-colors',
          'disabled:cursor-not-allowed',
          favorited
            ? 'border-rose-500/40 bg-rose-500/15 text-rose-300 hover:bg-rose-500/25'
            : 'border-slate-700 bg-slate-800/70 text-slate-300 hover:border-rose-500/40 hover:text-rose-300',
        )}
      >
        <Heart
          size={16}
          className={cn('transition-transform', favorited && 'scale-110 fill-current')}
        />
        {favorited ? '已收藏' : '收藏'}
      </button>
      {error ? <span className="text-xs text-rose-400">{error}</span> : null}
    </div>
  );
}
