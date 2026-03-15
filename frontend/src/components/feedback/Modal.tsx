'use client';

import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';

type ModalVariant = 'default' | 'destructive' | 'info';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children?: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm?: () => void;
  variant?: ModalVariant;
  loading?: boolean;
}

export function Modal({
  open,
  onClose,
  title,
  children,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  onConfirm,
  variant = 'default',
  loading = false,
}: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onClose]);

  useEffect(() => {
    document.body.style.overflow = open ? 'hidden' : '';
    return () => { document.body.style.overflow = ''; };
  }, [open]);

  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-end md:items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm animate-fade-in"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <div className="relative w-full max-w-md glass-card p-6 animate-scale-in">
        {/* Header */}
        <div className="flex items-start justify-between gap-3 mb-4">
          <h2 id="modal-title" className="text-lg font-display font-semibold text-[var(--text-primary)] leading-snug">
            {title}
          </h2>
          <button
            onClick={onClose}
            className="flex-shrink-0 min-w-[36px] min-h-[36px] flex items-center justify-center text-[var(--text-tertiary)] hover:text-[var(--text-primary)] rounded-lg hover:bg-[var(--bg-sunken)] transition-colors"
            aria-label="Close modal"
          >
            <Icon name="close" size="sm" />
          </button>
        </div>

        {children && (
          <div className="mb-6 text-sm text-[var(--text-secondary)] leading-relaxed">
            {children}
          </div>
        )}

        {onConfirm && (
          <div className="flex gap-3 justify-end">
            <Button variant="secondary" size="md" onClick={onClose} disabled={loading}>
              {cancelLabel}
            </Button>
            <Button
              variant={variant === 'destructive' ? 'danger' : 'primary'}
              size="md"
              onClick={onConfirm}
              loading={loading}
            >
              {confirmLabel}
            </Button>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
}
