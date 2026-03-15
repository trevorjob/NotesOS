import Link from 'next/link';
import { Icon } from '@/components/ui/Icon';
import { StatusBadge } from '@/components/feedback/StatusBadge';

type ResourceType = 'pdf' | 'image' | 'text' | 'handwritten' | 'other';

interface ResourceCardProps {
  id: string;
  topicId: string;
  courseId: string;
  title: string;
  type: ResourceType;
  isVerified?: boolean;
  pageCount?: number;
  createdAt?: string;
  className?: string;
}

const typeConfig: Record<ResourceType, { icon: string; label: string }> = {
  pdf:         { icon: 'picture_as_pdf', label: 'PDF' },
  image:       { icon: 'image',          label: 'Image' },
  text:        { icon: 'article',        label: 'Notes' },
  handwritten: { icon: 'draw',           label: 'Handwritten' },
  other:       { icon: 'attach_file',    label: 'File' },
};

export function ResourceCard({
  id,
  topicId,
  courseId,
  title,
  type,
  isVerified,
  pageCount,
  createdAt,
  className = '',
}: ResourceCardProps) {
  const cfg = typeConfig[type] ?? typeConfig.other;

  return (
    <Link
      href={`/courses/${courseId}/topics/${topicId}/resources/${id}`}
      className={`
        flex items-center gap-4 p-4 rounded-xl
        border border-[var(--border-base)] bg-[var(--bg-elevated)]
        hover:border-[var(--color-primary-muted)] hover:bg-[var(--color-primary-soft)]
        transition-all duration-150
        focus-ring
        ${className}
      `}
    >
      {/* Type icon */}
      <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-[var(--bg-sunken)] flex items-center justify-center">
        <Icon name={cfg.icon} size="sm" className="text-[var(--color-primary)]" />
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-[var(--text-primary)] truncate">{title}</p>
        <div className="flex items-center gap-2 mt-1">
          <StatusBadge variant="neutral" label={cfg.label} />
          {isVerified && (
            <StatusBadge variant="success" label="Verified" />
          )}
          {pageCount && (
            <span className="text-xs text-[var(--text-tertiary)]">{pageCount} p.</span>
          )}
        </div>
      </div>

      <Icon name="chevron_right" size="sm" className="text-[var(--text-tertiary)] flex-shrink-0" />
    </Link>
  );
}
