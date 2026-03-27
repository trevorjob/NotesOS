import { ButtonHTMLAttributes, forwardRef } from 'react';
import { Spinner } from './Spinner';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'filled' | 'ghost' | 'icon';
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'filled', size = 'md', loading, disabled, children, className = '', ...props }, ref) => {
    const base =
      'inline-flex items-center justify-center gap-2 font-serif font-medium rounded-lg border transition-all duration-150 cursor-pointer select-none focus-ring disabled:opacity-50 disabled:cursor-not-allowed';

    const variants = {
      filled:
        'bg-[#1a1917] text-white border-[#1a1917] hover:bg-[#2d2b28] active:bg-[#1a1917]',
      ghost:
        'bg-transparent text-[#1a1917] border-[#dedad4] hover:bg-[#e8e5e0] active:bg-[#dedad4]',
      icon:
        'bg-transparent text-[#6b6762] border-transparent hover:bg-[#e8e5e0] hover:text-[#1a1917] p-0',
    };

    const sizes = {
      sm: variant === 'icon' ? 'h-7 w-7 text-sm' : 'h-8 px-3 text-sm',
      md: variant === 'icon' ? 'h-9 w-9 text-base' : 'h-9 px-4 text-sm',
      lg: variant === 'icon' ? 'h-11 w-11 text-lg' : 'h-11 px-6 text-base',
    };

    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={`${base} ${variants[variant]} ${sizes[size]} ${className}`}
        {...props}
      >
        {loading ? <Spinner size="sm" /> : children}
      </button>
    );
  }
);

Button.displayName = 'Button';
