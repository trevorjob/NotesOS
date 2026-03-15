'use client';

import { forwardRef } from 'react';
import { Button } from './Button';

interface InviteCodeInputProps {
  value: string;
  onChange: (val: string) => void;
  onJoin: () => void;
  loading?: boolean;
  error?: string;
  placeholder?: string;
}

export const InviteCodeInput = forwardRef<HTMLInputElement, InviteCodeInputProps>(
  function InviteCodeInput({ value, onChange, onJoin, loading = false, error, placeholder = 'Enter invite code' }, ref) {
    return (
      <div className="flex flex-col gap-2">
        <div className="flex gap-2">
          <input
            ref={ref}
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value.toUpperCase())}
            placeholder={placeholder}
            maxLength={20}
            className={`
              flex-1 h-14 px-5
              rounded-xl border
              bg-[var(--bg-sunken)]
              text-[var(--text-primary)]
              placeholder:text-[var(--text-tertiary)]
              font-mono text-lg tracking-widest uppercase
              transition-colors
              focus:outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-muted)]
              ${error ? 'border-[var(--color-error)]' : 'border-[var(--border-base)]'}
            `}
            aria-invalid={!!error}
            onKeyDown={(e) => e.key === 'Enter' && onJoin()}
          />
          <Button
            onClick={onJoin}
            loading={loading}
            disabled={!value.trim()}
            size="lg"
          >
            Join
          </Button>
        </div>
        {error && (
          <p role="alert" className="text-xs text-[var(--color-error)]">{error}</p>
        )}
      </div>
    );
  }
);
