import Link from 'next/link';
import { Icon } from '@/components/ui/Icon';

interface SemesterGroupHeaderProps {
  id: string;
  name: string;
  startDate?: string | null;
  endDate?: string | null;
  memberCount?: number;
  courseCount?: number;
  className?: string;
}

function formatDateRange(start?: string | null, end?: string | null): string {
  const fmt = (d: string) =>
    new Date(d).toLocaleDateString(undefined, { month: 'short', year: 'numeric' });
  if (start && end)   return `${fmt(start)} – ${fmt(end)}`;
  if (start)          return `From ${fmt(start)}`;
  if (end)            return `Until ${fmt(end)}`;
  return '';
}

export function SemesterGroupHeader({
  id,
  name,
  startDate,
  endDate,
  memberCount,
  courseCount,
  className = '',
}: SemesterGroupHeaderProps) {
  const dateRange = formatDateRange(startDate, endDate);

  return (
    <div className={`flex items-center justify-between mb-3 ${className}`}>
      <div className="flex items-center gap-2">
        <Icon name="folder" size="sm" className="text-[var(--color-primary)]" filled />
        <div>
          <Link
            href={`/semesters/${id}`}
            className="text-sm font-bold text-[var(--text-primary)] hover:text-[var(--color-primary)] transition-colors"
          >
            {name}
          </Link>
          {dateRange && (
            <p className="text-xs text-[var(--text-tertiary)] mt-0.5">{dateRange}</p>
          )}
        </div>
      </div>
      <div className="flex items-center gap-3 text-xs text-[var(--text-tertiary)]">
        {memberCount !== undefined && (
          <span className="flex items-center gap-1">
            <Icon name="group" size="xs" />
            {memberCount}
          </span>
        )}
        {courseCount !== undefined && (
          <span className="flex items-center gap-1">
            <Icon name="school" size="xs" />
            {courseCount}
          </span>
        )}
      </div>
    </div>
  );
}
