import Link from 'next/link';
import { Icon } from '@/components/ui/Icon';

interface AIRecommendationBlockProps {
  topicTitle: string;
  topicId: string;
  courseId: string;
  reason?: string;
  className?: string;
}

export function AIRecommendationBlock({
  topicTitle,
  topicId,
  courseId,
  reason,
  className = '',
}: AIRecommendationBlockProps) {
  return (
    <div className={`flex items-start gap-3 p-4 rounded-xl bg-[var(--color-primary-soft)] border border-[var(--color-primary-muted)] ${className}`}>
      <div className="relative flex-shrink-0 mt-1">
        <span className="relative flex h-2.5 w-2.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[var(--color-primary)] opacity-60" />
          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-[var(--color-primary)]" />
        </span>
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-bold uppercase tracking-wider text-[var(--color-primary)] mb-1">
          AI Recommendation
        </p>
        <p className="text-sm font-semibold text-[var(--text-primary)]">{topicTitle}</p>
        {reason && (
          <p className="text-xs text-[var(--text-secondary)] mt-0.5 leading-snug">{reason}</p>
        )}
        <Link
          href={`/courses/${courseId}/topics/${topicId}`}
          className="inline-flex items-center gap-1 mt-2 text-xs font-semibold text-[var(--color-primary)] hover:underline"
        >
          Study this topic <Icon name="arrow_forward" size="xs" />
        </Link>
      </div>
    </div>
  );
}
