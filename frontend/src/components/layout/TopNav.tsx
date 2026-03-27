'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useAuthStore } from '@/stores/auth';
import { useProgressStore } from '@/stores/progress';
import { useNotificationStore } from '@/stores/notifications';
import { Avatar } from '@/components/ui/Avatar';

function NotificationBell() {
  const { unreadCount, notifications, markRead, markAllRead, fetchNotifications } = useNotificationStore();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchNotifications();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Close on outside click
  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  const recent = notifications.slice(0, 10);

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="relative p-2 rounded-lg hover:bg-[#f0eeea] transition-colors text-[#6b6762]"
        aria-label="Notifications"
      >
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
          <path
            d="M9 2a6 6 0 0 1 6 6v2.5l1 2H2l1-2V8a6 6 0 0 1 6-6Z"
            stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"
          />
          <path d="M7 14a2 2 0 0 0 4 0" stroke="currentColor" strokeWidth="1.5"/>
        </svg>
        {unreadCount > 0 && (
          <span className="absolute top-1 right-1 h-4 min-w-4 px-0.5 rounded-full bg-[#dc2626] text-white text-[10px] font-bold flex items-center justify-center leading-none">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 mt-1 w-80 bg-white border border-[#dedad4] rounded-2xl shadow-lg z-50 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-[#f0eeea]">
            <span className="text-sm font-semibold text-[#1a1917]">Notifications</span>
            {unreadCount > 0 && (
              <button
                onClick={() => markAllRead()}
                className="text-xs text-[#6b6762] hover:text-[#1a1917] transition-colors"
              >
                Mark all read
              </button>
            )}
          </div>

          <div className="max-h-80 overflow-y-auto">
            {recent.length === 0 ? (
              <p className="text-sm text-[#9e9a94] text-center py-8">No notifications yet.</p>
            ) : (
              recent.map((n) => (
                <button
                  key={n.id}
                  onClick={() => { if (!n.is_read) markRead(n.id); }}
                  className={`w-full text-left px-4 py-3 border-b border-[#f0eeea] last:border-0 transition-colors ${
                    n.is_read ? 'bg-white' : 'bg-[#fafaf9] hover:bg-[#f0eeea]'
                  }`}
                >
                  <div className="flex items-start gap-2.5">
                    <div className={`h-1.5 w-1.5 rounded-full mt-1.5 shrink-0 ${n.is_read ? 'opacity-0' : 'bg-[#1a1917]'}`} />
                    <div className="flex-1 min-w-0">
                      <p className={`text-sm ${n.is_read ? 'text-[#6b6762]' : 'font-medium text-[#1a1917]'}`}>{n.title}</p>
                      <p className="text-xs text-[#9e9a94] mt-0.5 truncate">{n.body}</p>
                      <p className="text-xs text-[#9e9a94] mt-0.5">
                        {new Date(n.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                      </p>
                    </div>
                  </div>
                </button>
              ))
            )}
          </div>

          <div className="px-4 py-2 border-t border-[#f0eeea]">
            <Link
              href="/settings#notifications"
              onClick={() => setOpen(false)}
              className="text-xs text-[#6b6762] hover:text-[#1a1917] transition-colors"
            >
              View all in settings →
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

interface TopNavProps {
  onMenuClick?: () => void;
}

export function TopNav({ onMenuClick }: TopNavProps) {
  const user = useAuthStore((s) => s.user);
  const streak = useProgressStore((s) => s.streak);

  return (
    <header className="h-14 bg-white border-b border-[#dedad4] flex items-center justify-between px-4 shrink-0">
      <div className="flex items-center gap-3">
        {/* Hamburger — mobile only */}
        <button
          onClick={onMenuClick}
          className="md:hidden p-2 -ml-1 rounded-lg hover:bg-[#f0eeea] transition-colors text-[#6b6762]"
          aria-label="Open menu"
        >
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M2 4h14M2 9h14M2 14h14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
        </button>

        {/* Logo */}
        <Link href="/home" className="text-[#1a1917] font-semibold text-base tracking-tight select-none">
          NotesOS
        </Link>
      </div>

      <div className="flex items-center gap-2">
        {/* Streak badge */}
        {streak > 0 && (
          <span className="text-sm text-[#6b6762] hidden sm:inline">
            🔥 <span className="font-medium text-[#1a1917]">{streak}</span> day streak
          </span>
        )}

        <NotificationBell />

        {/* Avatar → settings */}
        <Link href="/settings" aria-label="Settings">
          <Avatar name={user?.full_name} src={user?.avatar_url} size="sm" />
        </Link>
      </div>
    </header>
  );
}
