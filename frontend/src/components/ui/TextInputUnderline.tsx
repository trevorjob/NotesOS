'use client';

import { forwardRef } from 'react';

type InputSize = 'sm' | 'md' | 'lg';

interface TextInputUnderlineProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'size'> {
  label?: string;
  error?: string;
  size?: InputSize;
  serif?: boolean;
  containerClassName?: string;
}

const sizeClasses: Record<InputSize, string> = {
  sm: 'text-sm py-2',
  md: 'text-base py-3',
  lg: 'text-xl py-3',
};

export const TextInputUnderline = forwardRef<HTMLInputElement, TextInputUnderlineProps>(
  function TextInputUnderline(
    { label, error, size = 'md', serif = false, containerClassName = '', className = '', id, ...rest },
    ref
  ) {
    const inputId = id ?? `input-ul-${Math.random().toString(36).slice(2, 8)}`;

    return (
      <div className={`flex flex-col ${containerClassName}`}>
        {label && (
          <label
            htmlFor={inputId}
            className="text-xs uppercase tracking-widest text-[var(--text-tertiary)] mb-1"
          >
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={`
            w-full bg-transparent
            border-0 border-b
            border-[var(--border-base)]
            text-[var(--text-primary)]
            placeholder:text-[var(--text-tertiary)]
            focus:outline-none focus:border-[var(--color-primary)]
            transition-colors duration-150
            ${sizeClasses[size]}
            ${serif ? 'font-display' : ''}
            ${error ? 'border-[var(--color-error)]' : ''}
            ${className}
          `}
          aria-invalid={!!error}
          aria-describedby={error ? `${inputId}-error` : undefined}
          {...rest}
        />
        {error && (
          <p id={`${inputId}-error`} role="alert" className="text-xs text-[var(--color-error)] mt-1">
            {error}
          </p>
        )}
      </div>
    );
  }
);
