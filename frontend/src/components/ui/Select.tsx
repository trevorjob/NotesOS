'use client';

import { forwardRef } from 'react';

interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  options: SelectOption[];
  placeholder?: string;
  containerClassName?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  function Select(
    { label, error, options, placeholder, containerClassName = '', className = '', id, ...rest },
    ref
  ) {
    const inputId = id ?? `select-${Math.random().toString(36).slice(2, 8)}`;

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
        <select
          ref={ref}
          id={inputId}
          className={`
            w-full bg-transparent
            border-0 border-b border-[var(--border-base)]
            text-[var(--text-primary)] text-base
            py-3 pr-6
            appearance-none
            focus:outline-none focus:border-[var(--color-primary)]
            transition-colors duration-150
            cursor-pointer
            ${error ? 'border-[var(--color-error)]' : ''}
            ${className}
          `}
          {...rest}
        >
          {placeholder && (
            <option value="" disabled>
              {placeholder}
            </option>
          )}
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
        {error && (
          <p role="alert" className="text-xs text-[var(--color-error)] mt-1">{error}</p>
        )}
      </div>
    );
  }
);
