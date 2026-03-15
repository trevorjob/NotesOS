'use client';

import { useEffect, useState } from 'react';
import { Icon } from '@/components/ui/Icon';

interface TimerWidgetProps {
  durationSeconds: number;
  onExpire?: () => void;
  className?: string;
}

function pad(n: number): string {
  return String(n).padStart(2, '0');
}

export function TimerWidget({ durationSeconds, onExpire, className = '' }: TimerWidgetProps) {
  const [remaining, setRemaining] = useState(durationSeconds);

  useEffect(() => {
    if (remaining <= 0) {
      onExpire?.();
      return;
    }
    const interval = setInterval(() => setRemaining((r) => r - 1), 1000);
    return () => clearInterval(interval);
  }, [remaining, onExpire]);

  const mins = Math.floor(remaining / 60);
  const secs = remaining % 60;
  const isWarning = remaining <= 300;

  return (
    <span
      className={`
        flex items-center gap-1.5 px-3 py-1.5 rounded-full
        text-sm font-mono font-semibold
        ${isWarning
          ? 'bg-[var(--error-bg)] text-[var(--error-text)] animate-ping-slow'
          : 'bg-[var(--bg-sunken)] text-[var(--text-secondary)]'
        }
        ${className}
      `}
    >
      <Icon name="schedule" size="xs" />
      {pad(mins)}:{pad(secs)}
    </span>
  );
}
