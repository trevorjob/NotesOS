'use client';

import { useNotificationStore, type Toast } from '@/stores/notifications';

function ToastItem({ toast }: { toast: Toast }) {
  const dismiss = useNotificationStore((s) => s.dismissToast);

  const colors = {
    info: 'bg-[#1a1917] text-white',
    success: 'bg-[#16a34a] text-white',
    error: 'bg-[#dc2626] text-white',
  };

  return (
    <div
      className={`flex items-start gap-3 px-4 py-3 rounded-xl shadow-lg max-w-sm w-full animate-slide-up ${colors[toast.variant]}`}
    >
      <p className="flex-1 text-sm leading-snug">{toast.message}</p>
      <button
        onClick={() => dismiss(toast.id)}
        className="shrink-0 opacity-70 hover:opacity-100 transition-opacity text-base leading-none mt-0.5"
        aria-label="Dismiss"
      >
        ×
      </button>
    </div>
  );
}

export function ToastContainer() {
  const toasts = useNotificationStore((s) => s.toasts);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col gap-2 items-end">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} />
      ))}
    </div>
  );
}
