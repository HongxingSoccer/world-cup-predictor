'use client';

import { Link2, Share2 } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/Button';
import { apiPost } from '@/lib/api';
import type { ShareLinkResponse } from '@/types';

interface ShareButtonProps {
  targetType: 'prediction' | 'match' | 'track_record';
  targetId?: number;
  targetUrl: string;
  className?: string;
}

/**
 * Creates a tracked short link via the Java service and copies it to the
 * clipboard. Falls back to the raw `targetUrl` when the API call fails so
 * the user always gets *something* shareable.
 */
export function ShareButton({ targetType, targetId, targetUrl, className }: ShareButtonProps) {
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  const onClick = async () => {
    setBusy(true);
    setCopied(false);
    let urlToCopy = targetUrl;
    try {
      const res = await apiPost<ShareLinkResponse>('/api/v1/share/create', {
        targetType,
        targetId,
        targetUrl,
        utmSource: 'web',
        utmMedium: 'share-button',
      });
      urlToCopy = res.shareUrl;
    } catch {
      // Network / auth failure: fall back to the raw target URL below.
    }
    try {
      await navigator.clipboard.writeText(urlToCopy);
      setCopied(true);
      setTimeout(() => setCopied(false), 2_000);
    } catch {
      window.prompt('复制此链接以分享：', urlToCopy);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Button
      variant="secondary"
      size="sm"
      onClick={onClick}
      loading={busy}
      leftIcon={copied ? <Link2 size={16} /> : <Share2 size={16} />}
      className={className}
    >
      {copied ? '链接已复制' : '分享'}
    </Button>
  );
}
