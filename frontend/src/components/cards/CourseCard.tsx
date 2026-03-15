import Link from 'next/link';
import { LinearProgressBar } from '@/components/data-display/LinearProgressBar';
import { Icon } from '@/components/ui/Icon';

interface CourseCardProps {
  id: string;
  code: string;
  name: string;
  semester?: string;
  memberCount?: number;
  completionPercentage?: number;
  lastStudied?: string | null;
  state?: 'active' | 'archived';
  className?: string;
}

function relativeTime(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000 / 60 / 60 / 24;
  if (diff < 1)  return 'Today';
  if (diff < 2)  return 'Yesterday';
  if (diff < 7)  return `${Math.floor(diff)}d ago`;
  if (diff < 30) return `${Math.floor(diff / 7)}w ago`;
  return `${Math.floor(diff / 30)}mo ago`;
}

export function CourseCard({
  id,
  code,
  name,
  semester,
  memberCount,
  completionPercentage = 0,
  lastStudied,
  state = 'active',
  className = '',
}: CourseCardProps) {
  return (
    <Link
      href={`/courses/${id}`}
      className={`
        block glass-card p-5
        hover:shadow-[var(--shadow-primary)] hover:-translate-y-0.5
        transition-all duration-200
        focus-ring
        ${state === 'archived' ? 'opacity-60' : ''}
        ${className}
      `}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <p className="text-xs font-bold uppercase tracking-widest text-[var(--color-primary)] mb-1">
            {code}
          </p>
          <h3 className="font-display font-semibold text-base text-[var(--text-primary)] leading-snug line-clamp-2">
            {name}
          </h3>
        </div>
        {state === 'archived' && (
          <span className="flex-shrink-0 text-xs text-[var(--text-tertiary)] border border-[var(--border-base)] px-2 py-0.5 rounded-full">
            Archived
          </span>
        )}
      </div>

      {/* Progress */}
      <LinearProgressBar value={completionPercentage} size="thin" className="mb-3" />

      {/* Footer */}
      <div className="flex items-center gap-3 text-xs text-[var(--text-tertiary)]">
        <span className="font-semibold text-[var(--text-secondary)]">{completionPercentage}%</span>
        {semester && <span className="truncate">{semester}</span>}
        <span className="flex-1" />
        {memberCount !== undefined && (
          <span className="flex items-center gap-1">
            <Icon name="group" size="xs" />
            {memberCount}
          </span>
        )}
        {lastStudied && (
          <span className="flex items-center gap-1">
            <Icon name="schedule" size="xs" />
            {relativeTime(lastStudied)}
          </span>
        )}
      </div>
    </Link>
  );
}
