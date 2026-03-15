'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Icon } from '@/components/ui/Icon';

export interface Crumb {
  label: string;
  href?: string;
}

interface BreadcrumbProps {
  crumbs: Crumb[];
}

export function Breadcrumb({ crumbs }: BreadcrumbProps) {
  const router = useRouter();

  if (crumbs.length === 0) return null;

  return (
    <>
      {/* Mobile: back arrow */}
      <button
        onClick={() => router.back()}
        className="lg:hidden flex items-center justify-center min-w-[44px] min-h-[44px] -ml-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
        aria-label="Go back"
      >
        <Icon name="arrow_back" size="sm" />
      </button>

      {/* Desktop: full breadcrumb trail */}
      <nav aria-label="Breadcrumb" className="hidden lg:flex items-center gap-1">
        {crumbs.map((crumb, i) => {
          const isLast = i === crumbs.length - 1;
          return (
            <span key={i} className="flex items-center gap-1">
              {i > 0 && (
                <span className="text-[var(--text-tertiary)] text-sm select-none">/</span>
              )}
              {isLast || !crumb.href ? (
                <span
                  className={`text-sm ${
                    isLast
                      ? 'text-[var(--text-primary)] font-medium'
                      : 'text-[var(--text-secondary)]'
                  } max-w-[160px] truncate`}
                >
                  {crumb.label}
                </span>
              ) : (
                <Link
                  href={crumb.href}
                  className="text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors max-w-[160px] truncate"
                >
                  {crumb.label}
                </Link>
              )}
            </span>
          );
        })}
      </nav>
    </>
  );
}
