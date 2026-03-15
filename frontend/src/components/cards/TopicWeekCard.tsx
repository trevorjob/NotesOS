'use client';

import Link from 'next/link';
import { useState } from 'react';
import { Icon } from '@/components/ui/Icon';
import { LinearProgressBar } from '@/components/data-display/LinearProgressBar';

type TopicStatus = 'completed' | 'active' | 'not_started';

interface TopicWeekCardProps {
  id: string;
  courseId: string;
  title: string;
  weekNumber?: number;
  status?: TopicStatus;
  completionPercentage?: number;
  resourceCount?: number;
  onEdit?: (id: string) => void;
  onDelete?: (id: string) => void;
  className?: string;
}

const statusConfig: Record<TopicStatus, { icon: string; color: string; label: string }> = {
  completed:   { icon: 'check_circle', color: 'text-[var(--color-success)]',   label: 'Completed' },
  active:      { icon: 'play_circle',  color: 'text-[var(--color-primary)]',   label: 'In Progress' },
  not_started: { icon: 'radio_button_unchecked', color: 'text-[var(--text-tertiary)]', label: 'Not Started' },
};

export function TopicWeekCard({
  id,
  courseId,
  title,
  weekNumber,
  status = 'not_started',
  completionPercentage = 0,
  resourceCount = 0,
  onEdit,
  onDelete,
  className = '',
}: TopicWeekCardProps) {
  const [menuOpen, setMenuOpen] = useState(false);
  const cfg = statusConfig[status];

  return (
    <div
      className={`
        relative flex items-start gap-4 p-4 rounded-xl
        border border-[var(--border-base)]
        bg-[var(--bg-elevated)]
        hover:border-[var(--color-primary-muted)] hover:bg-[var(--color-primary-soft)]
        transition-all duration-150 group
        ${className}
      `}
    >
      {/* Status icon */}
      <div className="flex-shrink-0 mt-0.5">
        <Icon name={cfg.icon} size="sm" className={cfg.color} filled={status === 'completed'} />
      </div>

      {/* Content */}
      <Link href={`/courses/${courseId}/topics/${id}`} className="flex-1 min-w-0 focus-ring rounded-lg">
        <div className="flex items-center gap-2 mb-1">
          {weekNumber !== undefined && (
            <span className="text-[10px] uppercase tracking-wider font-bold text-[var(--text-tertiary)]">
              Week {weekNumber}
            </span>
          )}
        </div>
        <h3 className="text-sm font-semibold text-[var(--text-primary)] leading-snug mb-2 line-clamp-2">
          {title}
        </h3>
        <div className="flex items-center gap-3">
          <LinearProgressBar value={completionPercentage} size="thin" className="flex-1" />
          <span className="text-[10px] text-[var(--text-tertiary)] flex-shrink-0">
            {completionPercentage}%
          </span>
        </div>
        {resourceCount > 0 && (
          <p className="text-xs text-[var(--text-tertiary)] mt-1.5 flex items-center gap-1">
            <Icon name="description" size="xs" />
            {resourceCount} resource{resourceCount !== 1 ? 's' : ''}
          </p>
        )}
      </Link>

      {/* Three-dot menu */}
      {(onEdit || onDelete) && (
        <div className="relative">
          <button
            onClick={(e) => { e.preventDefault(); setMenuOpen((v) => !v); }}
            className="
              opacity-0 group-hover:opacity-100 transition-opacity
              min-w-[36px] min-h-[36px] flex items-center justify-center
              text-[var(--text-tertiary)] hover:text-[var(--text-primary)] rounded-lg hover:bg-[var(--bg-sunken)]
            "
            aria-label="Topic options"
          >
            <Icon name="more_vert" size="sm" />
          </button>

          {menuOpen && (
            <div className="absolute right-0 top-full mt-1 w-32 glass-card overflow-hidden z-10">
              {onEdit && (
                <button
                  onClick={() => { onEdit(id); setMenuOpen(false); }}
                  className="w-full flex items-center gap-2 px-3 py-2.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-sunken)] transition-colors"
                >
                  <Icon name="edit" size="xs" /> Edit
                </button>
              )}
              {onDelete && (
                <button
                  onClick={() => { onDelete(id); setMenuOpen(false); }}
                  className="w-full flex items-center gap-2 px-3 py-2.5 text-sm text-[var(--color-error)] hover:bg-[var(--error-bg)] transition-colors"
                >
                  <Icon name="delete" size="xs" /> Delete
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
