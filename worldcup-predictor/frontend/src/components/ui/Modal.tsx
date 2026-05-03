'use client';

import { X } from 'lucide-react';
import { useEffect, type ReactNode } from 'react';

import { cn } from '@/lib/utils';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  children: ReactNode;
  /** Max-width Tailwind utility (e.g. 'max-w-md', 'max-w-2xl'). */
  className?: string;
}

export function Modal({ open, onClose, title, children, className }: ModalProps) {
  // Close on ESC.
  useEffect(() => {
    if (!open) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  // Prevent background scroll while open.
  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
    >
      <button
        type="button"
        aria-label="关闭"
        className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm"
        onClick={onClose}
      />
      <div
        className={cn(
          'relative z-10 w-full max-w-md rounded-2xl bg-white p-6 shadow-xl',
          className,
        )}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute right-3 top-3 rounded-full p-1 text-slate-500 hover:bg-slate-100"
          aria-label="关闭"
        >
          <X size={18} />
        </button>
        {title ? <h2 className="mb-4 pr-10 text-lg font-semibold">{title}</h2> : null}
        {children}
      </div>
    </div>
  );
}
