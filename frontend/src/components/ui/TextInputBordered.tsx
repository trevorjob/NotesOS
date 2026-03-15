'use client';

import { forwardRef } from 'react';
import { Icon } from './Icon';

interface TextInputBorderedProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
  iconLeft?: string;
  iconRight?: string;
  onIconRightClick?: () => void;
  containerClassName?: string;
}

export const TextInputBordered = forwardRef<HTMLInputElement, TextInputBorderedProps>(
  function TextInputBordered(
    { label, error, hint, iconLeft, iconRight, onIconRightClick, containerClassName = '', className = '', id, ...rest },
    ref
  ) {
    const inputId = id ?? `input-${Math.random().toString(36).slice(2, 8)}`;

    return (
      <div className={`flex flex-col gap-1.5 ${containerClassName}`}>
        {label && (
          <label
            htmlFor={inputId}
            className="text-sm font-medium text-[var(--text-primary)]"
          >
            {label}
          </label>
        )}
        <div className="relative">
          {iconLeft && (
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)] pointer-events-none">
              <Icon name={iconLeft} size="sm" />
            </span>
          )}
          <input
            ref={ref}
            id={inputId}
            className={`
              w-full h-11 rounded-xl
              border border-[var(--border-base)]
              bg-[var(--bg-sunken)]
              text-sm text-[var(--text-primary)]
              placeholder:text-[var(--text-tertiary)]
              px-4
              ${iconLeft  ? 'pl-10' : ''}
              ${iconRight ? 'pr-10' : ''}
              transition-colors duration-150
              focus:outline-none focus:border-[var(--color-primary)] focus:ring-2 focus:ring-[var(--color-primary-muted)]
              ${error ? 'border-[var(--color-error)] focus:border-[var(--color-error)] focus:ring-[var(--error-bg)]' : ''}
              ${className}
            `}
            aria-invalid={!!error}
            aria-describedby={error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined}
            {...rest}
          />
          {iconRight && (
            <button
              type="button"
              onClick={onIconRightClick}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors"
              tabIndex={-1}
              aria-hidden={!onIconRightClick}
            >
              <Icon name={iconRight} size="sm" />
            </button>
          )}
        </div>
        {error && (
          <p id={`${inputId}-error`} role="alert" className="text-xs text-[var(--color-error)]">
            {error}
          </p>
        )}
        {!error && hint && (
          <p id={`${inputId}-hint`} className="text-xs text-[var(--text-tertiary)]">
            {hint}
          </p>
        )}
      </div>
    );
  }
);
