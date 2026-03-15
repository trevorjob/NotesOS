'use client';

import { Icon } from '@/components/ui/Icon';

export type ToastVariant = 'success' | 'error' | 'warning' | 'info';

export interface ToastItem {
  id: string;
  variant: ToastVariant;
  title: string;
  body?: string;
  duration?: number;
}

interface ToastProps {
  item: ToastItem;
  onDismiss: (id: string) => void;
}

const variantConfig: Record<ToastVariant, { icon: string; classes: string }> = {
  success: {
    icon: 'check_circle',
    classes: 'border-green-200 bg-[var(--success-bg)] text-[var(--success-text)]',
  },
  error: {
    icon: 'error',
    classes: 'border-red-200 bg-[var(--error-bg)] text-[var(--error-text)]',
  },
  warning: {
    icon: 'warning',
    classes: 'border-yellow-200 bg-[var(--warning-bg)] text-[var(--warning-text)]',
  },
  info: {
    icon: 'info',
    classes: 'border-blue-200 bg-[var(--info-bg)] text-[var(--info-text)]',
  },
};

export function Toast({ item, onDismiss }: ToastProps) {
  const config = variantConfig[item.variant];

  return (
    <div
      role="alert"
      className={`
        flex items-start gap-3 px-4 py-3
        rounded-xl border shadow-lg
        animate-slide-up
        min-w-[280px] max-w-[360px]
        ${config.classes}
      `}
    >
      <Icon name={config.icon} size="sm" className="flex-shrink-0 mt-0.5" filled />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold leading-snug">{item.title}</p>
        {item.body && (
          <p className="text-xs mt-0.5 opacity-80 leading-snug">{item.body}</p>
        )}
      </div>
      <button
        onClick={() => onDismiss(item.id)}
        className="flex-shrink-0 opacity-60 hover:opacity-100 transition-opacity min-w-[24px] min-h-[24px] flex items-center justify-center"
        aria-label="Dismiss"
      >
        <Icon name="close" size="xs" />
      </button>
    </div>
  );
}
