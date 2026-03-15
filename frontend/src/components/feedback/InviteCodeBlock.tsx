'use client';

import { useState } from 'react';
import { Icon } from '@/components/ui/Icon';

interface InviteCodeBlockProps {
  code: string;
  active?: boolean;
  className?: string;
}

export function InviteCodeBlock({ code, active = true, className = '' }: InviteCodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className={`flex items-center gap-3 p-4 rounded-xl border ${active ? 'border-[var(--color-primary-muted)] bg-[var(--color-primary-soft)]' : 'border-[var(--border-base)] bg-[var(--bg-sunken)] opacity-60'} ${className}`}>
      <code className="flex-1 font-mono text-xl font-bold tracking-[0.25em] text-[var(--color-primary)]">
        {code}
      </code>
      <button
        onClick={handleCopy}
        disabled={!active}
        className="
          flex items-center gap-1.5 px-3 py-2 rounded-lg
          text-xs font-semibold
          bg-[var(--color-primary-muted)] text-[var(--color-primary)]
          hover:bg-[var(--color-primary)] hover:text-white
          transition-all duration-150
          min-h-[36px]
        "
        aria-label="Copy invite code"
      >
        <Icon name={copied ? 'check' : 'content_copy'} size="xs" />
        {copied ? 'Copied!' : 'Copy'}
      </button>
    </div>
  );
}
