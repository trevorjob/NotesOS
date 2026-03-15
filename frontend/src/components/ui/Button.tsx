import { Icon } from './Icon';

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  iconLeft?: string;
  iconRight?: string;
  fullWidth?: boolean;
  className?: string;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary: `
    bg-[var(--color-primary)] text-white
    hover:bg-[var(--color-primary-hover)]
    shadow-[var(--shadow-primary)]
    hover:shadow-lg
  `,
  secondary: `
    bg-[var(--bg-elevated)] text-[var(--text-primary)]
    border border-[var(--border-base)]
    hover:bg-[var(--bg-sunken)]
  `,
  ghost: `
    bg-transparent text-[var(--text-secondary)]
    hover:bg-[var(--bg-sunken)] hover:text-[var(--text-primary)]
  `,
  danger: `
    bg-[var(--color-error)] text-white
    hover:opacity-90
    shadow-sm
  `,
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'h-9 px-3.5 text-sm rounded-lg gap-1.5',
  md: 'h-11 px-5 text-sm rounded-xl gap-2',
  lg: 'h-[52px] px-7 text-base rounded-xl gap-2',
};

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  iconLeft,
  iconRight,
  fullWidth = false,
  className = '',
  children,
  disabled,
  ...rest
}: ButtonProps) {
  const isDisabled = disabled || loading;

  return (
    <button
      disabled={isDisabled}
      className={`
        inline-flex items-center justify-center font-semibold
        min-w-[44px] min-h-[44px]
        transition-all duration-150
        focus-ring
        ${sizeClasses[size]}
        ${variantClasses[variant]}
        ${fullWidth ? 'w-full' : ''}
        ${isDisabled ? 'opacity-50 cursor-not-allowed pointer-events-none' : 'cursor-pointer'}
        ${className}
      `}
      {...rest}
    >
      {loading ? (
        <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
      ) : iconLeft ? (
        <Icon name={iconLeft} size="xs" />
      ) : null}
      {children}
      {!loading && iconRight && <Icon name={iconRight} size="xs" />}
    </button>
  );
}
