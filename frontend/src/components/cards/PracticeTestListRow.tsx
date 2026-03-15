import Link from 'next/link';
import { Icon } from '@/components/ui/Icon';
import { StatusBadge } from '@/components/feedback/StatusBadge';

interface PracticeTestListRowProps {
  id: string;
  attemptId?: string;
  title?: string;
  date: string;
  score?: number | null;
  questionCount: number;
  status: 'graded' | 'pending' | 'draft';
  className?: string;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function getScoreColor(score: number): 'success' | 'warning' | 'error' {
  if (score >= 85) return 'success';
  if (score >= 60) return 'warning';
  return 'error';
}

export function PracticeTestListRow({
  id,
  attemptId,
  title,
  date,
  score,
  questionCount,
  status,
  className = '',
}: PracticeTestListRowProps) {
  const href = attemptId ? `/practice/${attemptId}/results` : `/practice/${id}`;

  return (
    <Link
      href={href}
      className={`
        flex items-center gap-4 p-4 rounded-xl
        border border-[var(--border-base)] bg-[var(--bg-elevated)]
        hover:border-[var(--color-primary-muted)] hover:bg-[var(--color-primary-soft)]
        transition-all duration-150
        focus-ring
        ${className}
      `}
    >
      {/* Score ring */}
      <div className={`
        flex-shrink-0 w-12 h-12 rounded-full border-2 flex items-center justify-center
        ${status === 'graded' && score !== null && score !== undefined
          ? `border-[var(--color-${getScoreColor(score)})]`
          : 'border-[var(--border-base)]'
        }
      `}>
        {status === 'graded' && score !== null && score !== undefined ? (
          <span className="text-sm font-bold text-[var(--text-primary)]">{score}%</span>
        ) : status === 'pending' ? (
          <Icon name="hourglass_empty" size="sm" className="text-[var(--text-tertiary)]" />
        ) : (
          <Icon name="edit_note" size="sm" className="text-[var(--text-tertiary)]" />
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-[var(--text-primary)] truncate">
          {title ?? `Practice Test`}
        </p>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-xs text-[var(--text-tertiary)]">{formatDate(date)}</span>
          <span className="text-[var(--text-tertiary)]">·</span>
          <span className="text-xs text-[var(--text-tertiary)]">{questionCount} questions</span>
        </div>
      </div>

      <div className="flex-shrink-0 flex items-center gap-2">
        {status === 'pending' && <StatusBadge variant="info" label="Grading" pulse />}
        {status === 'draft'   && <StatusBadge variant="neutral" label="Draft" />}
        <Icon name="chevron_right" size="sm" className="text-[var(--text-tertiary)]" />
      </div>
    </Link>
  );
}
