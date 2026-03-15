'use client';

import { useState } from 'react';
import { Icon } from '@/components/ui/Icon';
import { NotificationDropdown } from './NotificationDropdown';

interface NotificationBellProps {
  unreadCount?: number;
}

export function NotificationBell({ unreadCount = 0 }: NotificationBellProps) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label={`Notifications${unreadCount > 0 ? `, ${unreadCount} unread` : ''}`}
        className="
          relative flex items-center justify-center
          min-w-[44px] min-h-[44px] rounded-full
          text-[var(--text-secondary)]
          hover:bg-[var(--bg-sunken)] hover:text-[var(--text-primary)]
          transition-colors focus-ring
        "
      >
        <Icon name="notifications" size="sm" />
        {unreadCount > 0 && (
          <span
            className="
              absolute top-2 right-2
              min-w-[16px] h-4 px-1
              rounded-full bg-[var(--color-error)]
              text-white text-[10px] font-bold
              flex items-center justify-center
              leading-none
            "
          >
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      <NotificationDropdown open={open} onClose={() => setOpen(false)} />
    </div>
  );
}
