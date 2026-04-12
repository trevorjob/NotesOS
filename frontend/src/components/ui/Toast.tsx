'use client';

import { useNotificationStore, type Toast } from '@/stores/notifications';

const icons = {
  success: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="shrink-0 mt-0.5">
      <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5" strokeOpacity="0.6"/>
      <path d="M5 8l2 2 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  error: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="shrink-0 mt-0.5">
      <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5" strokeOpacity="0.6"/>
      <path d="M5.5 5.5l5 5M10.5 5.5l-5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),
  info: (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="shrink-0 mt-0.5">
      <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5" strokeOpacity="0.6"/>
      <path d="M8 7v4M8 5.5v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),
};

const styles = {
  success: 'bg-[#1a1917] text-white border border-white/10',
  error:   'bg-[#dc2626] text-white border border-white/10',
  info:    'bg-[#1a1917] text-white border border-white/10',
};

function ToastItem({ toast }: { toast: Toast }) {
  const dismiss = useNotificationStore((s) => s.dismissToast);

  return (
    <div className={`flex items-start gap-3 pl-3.5 pr-3 py-3 rounded-xl shadow-lg w-[300px] animate-slide-up ${styles[toast.variant]}`}>
      {icons[toast.variant]}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium leading-snug">{toast.title}</p>
        {toast.body && (
          <p className="text-xs mt-0.5 opacity-70 leading-snug">{toast.body}</p>
        )}
      </div>
      <button
        onClick={() => dismiss(toast.id)}
        className="shrink-0 opacity-50 hover:opacity-100 transition-opacity leading-none mt-0.5"
        aria-label="Dismiss"
      >
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
          <path d="M1 1l10 10M11 1L1 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
        </svg>
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
