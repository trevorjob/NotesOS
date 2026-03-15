import Link from 'next/link';
import { Icon } from '@/components/ui/Icon';

interface TestResultsNextStepBlockProps {
  topicTitle: string;
  topicId: string;
  courseId: string;
  action?: string;
  className?: string;
}

export function TestResultsNextStepBlock({
  topicTitle,
  topicId,
  courseId,
  action = 'Review this topic',
  className = '',
}: TestResultsNextStepBlockProps) {
  return (
    <div className={`flex items-start gap-3 p-4 rounded-xl bg-[var(--info-bg)] border border-blue-100 ${className}`}>
      <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-[var(--color-info)] flex items-center justify-center mt-0.5">
        <Icon name="lightbulb" size="xs" className="text-white" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-bold uppercase tracking-wider text-[var(--info-text)] mb-1">
          Next Step
        </p>
        <p className="text-sm font-semibold text-[var(--text-primary)]">{topicTitle}</p>
        <Link
          href={`/courses/${courseId}/topics/${topicId}`}
          className="inline-flex items-center gap-1 mt-2 text-xs font-semibold text-[var(--info-text)] hover:underline"
        >
          {action} <Icon name="arrow_forward" size="xs" />
        </Link>
      </div>
    </div>
  );
}
