'use client';

import { Icon } from '@/components/ui/Icon';
import { Button } from '@/components/ui/Button';

interface AIPreClassResearchCardProps {
  summary?: string | null;
  loading?: boolean;
  onGenerate?: () => void;
  generating?: boolean;
  className?: string;
}

export function AIPreClassResearchCard({
  summary,
  loading = false,
  onGenerate,
  generating = false,
  className = '',
}: AIPreClassResearchCardProps) {
  return (
    <div
      className={`
        rounded-2xl p-5
        border-l-4 border-[var(--color-purple)]
        bg-gradient-to-br from-purple-50/60 to-[var(--bg-elevated)]
        dark:from-purple-900/20
        shadow-soft
        ${className}
      `}
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-3">
        <div className="w-7 h-7 rounded-lg bg-[var(--color-purple)] flex items-center justify-center">
          <Icon name="auto_awesome" size="xs" className="text-white" />
        </div>
        <span className="text-xs font-bold uppercase tracking-widest text-[var(--color-purple)]">
          AI Pre-Class Research
        </span>
      </div>

      {loading ? (
        <div className="space-y-2">
          <div className="h-3 bg-[var(--border-base)] rounded animate-pulse w-full" />
          <div className="h-3 bg-[var(--border-base)] rounded animate-pulse w-4/5" />
          <div className="h-3 bg-[var(--border-base)] rounded animate-pulse w-3/4" />
        </div>
      ) : summary ? (
        <p className="text-sm text-[var(--text-secondary)] leading-relaxed">{summary}</p>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-sm text-[var(--text-secondary)]">
            Get an AI-generated research summary to prepare for this topic.
          </p>
          {onGenerate && (
            <Button
              variant="ghost"
              size="sm"
              onClick={onGenerate}
              loading={generating}
              iconLeft="auto_awesome"
              className="self-start text-[var(--color-purple)] hover:bg-purple-50 dark:hover:bg-purple-900/20"
            >
              Generate Research
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
