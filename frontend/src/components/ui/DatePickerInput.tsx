'use client';

import { forwardRef } from 'react';

interface DatePickerInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  containerClassName?: string;
}

export const DatePickerInput = forwardRef<HTMLInputElement, DatePickerInputProps>(
  function DatePickerInput({ label, error, containerClassName = '', className = '', id, ...rest }, ref) {
    const inputId = id ?? `date-${Math.random().toString(36).slice(2, 8)}`;

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
          type="date"
          className={`
            w-full bg-transparent
            border-0 border-b border-[var(--border-base)]
            text-[var(--text-primary)] text-base
            py-3
            focus:outline-none focus:border-[var(--color-primary)]
            transition-colors duration-150
            ${error ? 'border-[var(--color-error)]' : ''}
            ${className}
          `}
          {...rest}
        />
        {error && (
          <p role="alert" className="text-xs text-[var(--color-error)] mt-1">{error}</p>
        )}
      </div>
    );
  }
);
