'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Avatar } from '@/components/data-display/Avatar';
import { Breadcrumb, Crumb } from './Breadcrumb';
import { NotificationBell } from '@/components/modals/NotificationBell';
import { Icon } from '@/components/ui/Icon';
import { useAuthStore } from '@/stores/auth';

/* ── App TopBar (main layout) ─────────────────────────────────────────── */

interface AppTopBarProps {
  breadcrumb?: Crumb[];
  unreadCount?: number;
}

export function AppTopBar({ breadcrumb = [], unreadCount = 0 }: AppTopBarProps) {
  const user = useAuthStore((s) => s.user);

  return (
    <header
      className="
        glass-nav fixed top-0 left-0 right-0 z-40
        h-[60px] pt-[env(safe-area-inset-top)]
        lg:left-[64px]
        flex items-center px-4 md:px-6 gap-3
      "
    >
      {/* Left: back arrow (mobile) or breadcrumb (desktop) */}
      <div className="flex-1 flex items-center gap-2 min-w-0">
        <Breadcrumb crumbs={breadcrumb} />
      </div>

      {/* Right: Bell + Avatar */}
      <div className="flex items-center gap-1">
        <NotificationBell unreadCount={unreadCount} />
        <Link
          href="/profile"
          aria-label="Profile"
          className="min-w-[44px] min-h-[44px] flex items-center justify-center"
        >
          <Avatar name={user?.full_name ?? 'User'} size="sm" />
        </Link>
      </div>
    </header>
  );
}

/* ── Test TopBar (immersive layout — take test) ──────────────────────── */

interface TestTopBarProps {
  onExit: () => void;
  current: number;
  total: number;
  timerEl?: React.ReactNode;
}

export function TestTopBar({ onExit, current, total, timerEl }: TestTopBarProps) {
  return (
    <header
      className="
        glass-nav fixed top-0 left-0 right-0 z-40
        h-[60px] pt-[env(safe-area-inset-top)]
        flex items-center justify-between px-4 gap-3
      "
    >
      <button
        onClick={onExit}
        className="flex items-center gap-1.5 min-w-[44px] min-h-[44px] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
        aria-label="Exit test"
      >
        <Icon name="close" size="sm" />
        <span className="text-sm hidden sm:inline">Exit</span>
      </button>

      <span className="text-xs font-bold uppercase tracking-widest text-[var(--color-primary)] bg-[var(--color-primary-muted)] px-3 py-1 rounded-full">
        Question {current} of {total}
      </span>

      <div className="min-w-[44px] flex justify-end">
        {timerEl}
      </div>
    </header>
  );
}

/* ── Reading TopBar (immersive layout — resource detail) ─────────────── */

interface ReadingTopBarProps {
  title: string;
  onExit: () => void;
  onToggleTheme: () => void;
  isDark: boolean;
}

export function ReadingTopBar({ title, onExit, onToggleTheme, isDark }: ReadingTopBarProps) {
  const router = useRouter();

  return (
    <header
      className="
        glass-nav fixed top-0 left-0 right-0 z-40
        h-[60px] pt-[env(safe-area-inset-top)]
        flex items-center justify-between px-4 gap-3
      "
    >
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1.5 min-w-[44px] min-h-[44px] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
        aria-label="Exit resource"
      >
        <Icon name="close" size="sm" />
      </button>

      <span className="flex-1 text-sm font-medium text-[var(--text-primary)] truncate text-center px-2">
        {title}
      </span>

      <button
        onClick={onToggleTheme}
        className="min-w-[44px] min-h-[44px] flex items-center justify-center text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
        aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
      >
        <Icon name={isDark ? 'light_mode' : 'dark_mode'} size="sm" />
      </button>
    </header>
  );
}
