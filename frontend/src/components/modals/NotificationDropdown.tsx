'use client';

import { useEffect, useRef, useState } from 'react';
import { Icon } from '@/components/ui/Icon';
import { apiClient } from '@/lib/api';

interface Notification {
  id: string;
  type: string;
  title: string;
  body: string;
  is_read: boolean;
  created_at: string;
  meta_data?: Record<string, string> | null;
}

interface NotificationDropdownProps {
  open: boolean;
  onClose: () => void;
}

const typeIcon: Record<string, string> = {
  TEST_GRADED: 'grade',
  AI_SUMMARY_READY: 'auto_awesome',
  INVITE_ACCEPTED: 'group_add',
  GENERAL: 'notifications',
};

function relativeTime(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export function NotificationDropdown({ open, onClose }: NotificationDropdownProps) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    apiClient
      .get('/api/notifications')
      .then((r) => setNotifications(r.data.notifications ?? []))
      .catch(() => { })
      .finally(() => setLoading(false));
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open, onClose]);

  if (!open) return null;

  const markAllRead = async () => {
    try {
      await apiClient.patch('/api/notifications/read-all');
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    } catch { }
  };

  const unread = notifications.filter((n) => !n.is_read).length;

  return (
    <div
      ref={ref}
      className="
        absolute right-0 top-full mt-2
        w-[340px] max-h-[420px]
        glass-card overflow-hidden
        flex flex-col
        z-50 animate-slide-down
      "
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border-base)]">
        <span className="text-sm font-semibold text-[var(--text-primary)]">Notifications</span>
        {unread > 0 && (
          <button
            onClick={markAllRead}
            className="text-xs text-[var(--color-primary)] hover:underline transition-colors"
          >
            Mark all read
          </button>
        )}
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center py-10">
            <span className="text-xs text-[var(--text-tertiary)]">Loading…</span>
          </div>
        ) : notifications.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-10 px-4 text-center">
            <Icon name="notifications_none" size="lg" className="text-[var(--text-tertiary)]" />
            <p className="text-sm text-[var(--text-secondary)]">You're all caught up</p>
          </div>
        ) : (
          notifications.map((n) => (
            <div
              key={n.id}
              className={`
                flex items-start gap-3 px-4 py-3
                border-b border-[var(--border-base)] last:border-0
                transition-colors hover:bg-[var(--bg-sunken)]
                ${!n.is_read ? 'bg-[var(--color-primary-soft)]' : ''}
              `}
            >
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-[var(--color-primary-muted)] flex items-center justify-center mt-0.5">
                <Icon name={typeIcon[n.type] ?? 'notifications'} size="xs" className="text-[var(--color-primary)]" filled />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-[var(--text-primary)] leading-snug">{n.title}</p>
                <p className="text-xs text-[var(--text-secondary)] mt-0.5 leading-snug line-clamp-2">{n.body}</p>
                <p className="text-[10px] text-[var(--text-tertiary)] mt-1 uppercase tracking-wider">
                  {relativeTime(n.created_at)}
                </p>
              </div>
              {!n.is_read && (
                <div className="flex-shrink-0 w-2 h-2 rounded-full bg-[var(--color-primary)] mt-2" />
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
