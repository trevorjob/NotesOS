'use client';

import { useState } from 'react';
import { Icon } from '@/components/ui/Icon';
import { StatusBadge } from '@/components/feedback/StatusBadge';
import { LinearProgressBar } from '@/components/data-display/LinearProgressBar';

type AnswerStatus = 'CORRECT' | 'PARTIAL' | 'NEEDS_REVIEW';

interface TestResultQuestionCardProps {
  questionNumber: number;
  questionText: string;
  yourAnswer: string;
  feedback: string;
  score: number;
  status: AnswerStatus;
  keyPointsCovered?: string[];
  keyPointsMissed?: string[];
  encouragement?: string;
  className?: string;
}

const statusConfig: Record<AnswerStatus, { badge: 'success' | 'warning' | 'error'; icon: string; label: string }> = {
  CORRECT:      { badge: 'success', icon: 'check_circle', label: 'Correct' },
  PARTIAL:      { badge: 'warning', icon: 'check_circle',  label: 'Partial' },
  NEEDS_REVIEW: { badge: 'error',   icon: 'cancel',        label: 'Needs Review' },
};

export function TestResultQuestionCard({
  questionNumber,
  questionText,
  yourAnswer,
  feedback,
  score,
  status,
  keyPointsCovered = [],
  keyPointsMissed = [],
  encouragement,
  className = '',
}: TestResultQuestionCardProps) {
  const [expanded, setExpanded] = useState(false);
  const cfg = statusConfig[status];
  const scorePct = Math.round(score * 10);

  return (
    <div className={`glass-card overflow-hidden ${className}`}>
      {/* Header */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="
          w-full flex items-center gap-4 p-5
          text-left hover:bg-[var(--bg-sunken)]
          transition-colors
        "
        aria-expanded={expanded}
      >
        <div className="flex-shrink-0 w-7 h-7 rounded-full bg-[var(--bg-sunken)] flex items-center justify-center">
          <span className="text-xs font-bold text-[var(--text-secondary)]">{questionNumber}</span>
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm text-[var(--text-primary)] font-medium line-clamp-1">{questionText}</p>
          <LinearProgressBar value={scorePct} size="thin" className="mt-2 max-w-[120px]" />
        </div>
        <StatusBadge variant={cfg.badge} label={cfg.label} className="flex-shrink-0" />
        <Icon name={expanded ? 'expand_less' : 'expand_more'} size="sm" className="text-[var(--text-tertiary)] flex-shrink-0" />
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="px-5 pb-5 border-t border-[var(--border-base)] pt-4 space-y-4">
          <div>
            <p className="text-xs uppercase tracking-wider font-bold text-[var(--text-tertiary)] mb-1">Your Answer</p>
            <p className="text-sm text-[var(--text-secondary)] leading-relaxed">{yourAnswer}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wider font-bold text-[var(--text-tertiary)] mb-1">AI Feedback</p>
            <p className="text-sm text-[var(--text-primary)] leading-relaxed">{feedback}</p>
          </div>
          {keyPointsCovered.length > 0 && (
            <div>
              <p className="text-xs uppercase tracking-wider font-bold text-[var(--success-text)] mb-1.5">Key Points Covered</p>
              <ul className="space-y-1">
                {keyPointsCovered.map((pt, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-[var(--text-primary)]">
                    <Icon name="check" size="xs" className="text-[var(--color-success)] mt-0.5 flex-shrink-0" />
                    {pt}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {keyPointsMissed.length > 0 && (
            <div>
              <p className="text-xs uppercase tracking-wider font-bold text-[var(--error-text)] mb-1.5">Key Points Missed</p>
              <ul className="space-y-1">
                {keyPointsMissed.map((pt, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-[var(--text-primary)]">
                    <Icon name="close" size="xs" className="text-[var(--color-error)] mt-0.5 flex-shrink-0" />
                    {pt}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {encouragement && (
            <p className="text-sm text-[var(--color-primary)] italic font-display">{encouragement}</p>
          )}
        </div>
      )}
    </div>
  );
}
