'use client';

import { forwardRef } from 'react';

type TextareaVariant = 'form' | 'essay';

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  hint?: string;
  variant?: TextareaVariant;
  containerClassName?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  function Textarea(
    { label, error, hint, variant = 'form', containerClassName = '', className = '', id, ...rest },
    ref
  ) {
    const inputId = id ?? `textarea-${Math.random().toString(36).slice(2, 8)}`;

    return (
      <div className={`flex flex-col gap-1.5 ${containerClassName}`}>
        {label && (
          <label htmlFor={inputId} className="text-sm font-medium text-[var(--text-primary)]">
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          id={inputId}
          className={`
            w-full rounded-xl
            border border-[var(--border-base)]
            bg-[var(--bg-sunken)]
            text-[var(--text-primary)]
            placeholder:text-[var(--text-tertiary)]
            p-4 resize-none
            transition-colors duration-150
            focus:outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-muted)]
            ${error ? 'border-[var(--color-error)]' : ''}
            ${variant === 'essay' ? 'min-h-[200px] text-base leading-relaxed font-display' : 'min-h-[100px] text-sm'}
            ${className}
          `}
          aria-invalid={!!error}
          aria-describedby={error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined}
          {...rest}
        />
        {error && (
          <p id={`${inputId}-error`} role="alert" className="text-xs text-[var(--color-error)]">
            {error}
          </p>
        )}
        {!error && hint && (
          <p id={`${inputId}-hint`} className="text-xs text-[var(--text-tertiary)]">{hint}</p>
        )}
      </div>
    );
  }
);
