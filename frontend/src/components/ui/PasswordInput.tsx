'use client';

import { forwardRef, useState } from 'react';
import { TextInputUnderline } from './TextInputUnderline';
import { Icon } from './Icon';

interface PasswordInputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type' | 'size'> {
  label?: string;
  error?: string;
  size?: 'sm' | 'md' | 'lg';
  containerClassName?: string;
}

export const PasswordInput = forwardRef<HTMLInputElement, PasswordInputProps>(
  function PasswordInput({ label = 'Password', error, containerClassName = '', ...rest }, ref) {
    const [visible, setVisible] = useState(false);

    return (
      <div className={`relative ${containerClassName}`}>
        <TextInputUnderline
          ref={ref}
          type={visible ? 'text' : 'password'}
          label={label}
          error={error}
          className="pr-10"
          {...rest}
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? 'Hide password' : 'Show password'}
          className="
            absolute right-0 bottom-3
            text-[var(--text-tertiary)] hover:text-[var(--text-primary)]
            transition-colors min-w-[24px] min-h-[24px]
            flex items-center justify-center
          "
        >
          <Icon name={visible ? 'visibility_off' : 'visibility'} size="sm" />
        </button>
      </div>
    );
  }
);
