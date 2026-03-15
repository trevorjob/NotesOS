'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Icon } from '@/components/ui/Icon';

interface NavItem {
  href: string;
  icon: string;
  label: string;
  matchPrefix?: string;
}

const NAV_ITEMS: NavItem[] = [
  { href: '/courses',  icon: 'school',  label: 'Courses',  matchPrefix: '/courses' },
  { href: '/semesters', icon: 'folder', label: 'Semesters', matchPrefix: '/semesters' },
  { href: '/practice', icon: 'quiz',   label: 'Practice', matchPrefix: '/practice' },
  { href: '/profile',  icon: 'person', label: 'Profile',  matchPrefix: '/profile' },
];

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav
      className="
        lg:hidden
        fixed bottom-0 left-0 right-0 z-40
        pb-[env(safe-area-inset-bottom)]
        bg-[var(--bg-elevated)]
        border-t border-[var(--border-base)]
        flex items-center justify-around
      "
      aria-label="Bottom navigation"
    >
      {NAV_ITEMS.map((item) => {
        const active = item.matchPrefix
          ? pathname.startsWith(item.matchPrefix)
          : pathname === item.href;

        return (
          <Link
            key={item.href}
            href={item.href}
            aria-label={item.label}
            className={`
              flex flex-col items-center justify-center gap-0.5
              min-w-[56px] h-[64px] px-3
              transition-colors
              ${active
                ? 'text-[var(--color-primary)]'
                : 'text-[var(--text-tertiary)]'
              }
            `}
          >
            <Icon name={item.icon} size="sm" filled={active} />
            <span className="text-[10px] font-medium uppercase tracking-wider leading-none">
              {item.label}
            </span>
          </Link>
        );
      })}
    </nav>
  );
}
