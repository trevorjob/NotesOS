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
  { href: '/courses', icon: 'school',      label: 'Courses',   matchPrefix: '/courses' },
  { href: '/semesters', icon: 'folder',    label: 'Semesters', matchPrefix: '/semesters' },
  { href: '/practice', icon: 'quiz',       label: 'Practice',  matchPrefix: '/practice' },
  { href: '/profile',  icon: 'person',     label: 'Profile',   matchPrefix: '/profile' },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside
      className="
        hidden lg:flex
        fixed left-0 top-0 bottom-0 z-50
        w-[64px]
        flex-col items-center
        border-r border-[var(--border-base)]
        bg-[var(--bg-elevated)]
        pt-[env(safe-area-inset-top)]
      "
    >
      {/* Logo */}
      <div className="flex items-center justify-center w-full h-[60px] border-b border-[var(--border-base)]">
        <div className="w-8 h-8 rounded-lg bg-[var(--color-primary)] flex items-center justify-center">
          <span className="font-display font-bold text-white text-sm">N</span>
        </div>
      </div>

      {/* Nav items */}
      <nav className="flex flex-col items-center gap-1 p-2 pt-3 flex-1" aria-label="Main navigation">
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
                relative group
                flex items-center justify-center
                w-12 h-12 rounded-xl
                transition-all duration-150
                ${active
                  ? 'bg-[var(--color-primary-muted)] text-[var(--color-primary)]'
                  : 'text-[var(--text-secondary)] hover:bg-[var(--bg-sunken)] hover:text-[var(--text-primary)]'
                }
              `}
            >
              <Icon name={item.icon} size="sm" filled={active} />

              {/* Tooltip */}
              <span className="
                pointer-events-none
                absolute left-full ml-2 px-2 py-1
                bg-[var(--bg-elevated)] border border-[var(--border-base)]
                text-xs text-[var(--text-primary)] rounded-md shadow-md
                whitespace-nowrap
                opacity-0 scale-95
                group-hover:opacity-100 group-hover:scale-100
                transition-all origin-left
                z-10
              ">
                {item.label}
              </span>

              {active && (
                <span className="absolute right-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-[var(--color-primary)] rounded-full" />
              )}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
