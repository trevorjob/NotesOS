import { Icon } from './Icon';

type IconButtonVariant = 'ghost' | 'filled' | 'primary';

interface IconButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon: string;
  label: string;
  variant?: IconButtonVariant;
  size?: 'sm' | 'md' | 'lg';
  filled?: boolean;
  className?: string;
}

const variantClasses: Record<IconButtonVariant, string> = {
  ghost: 'bg-transparent text-[var(--text-secondary)] hover:bg-[var(--bg-sunken)] hover:text-[var(--text-primary)]',
  filled: 'bg-[var(--bg-sunken)] text-[var(--text-primary)] hover:bg-[var(--border-base)]',
  primary: 'bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary-hover)]',
};

const sizeClasses = {
  sm: 'w-9 h-9 rounded-lg',
  md: 'w-11 h-11 rounded-xl',
  lg: 'w-12 h-12 rounded-xl',
};

export function IconButton({
  icon,
  label,
  variant = 'ghost',
  size = 'md',
  filled = false,
  className = '',
  ...rest
}: IconButtonProps) {
  return (
    <button
      aria-label={label}
      className={`
        inline-flex items-center justify-center flex-shrink-0
        min-w-[44px] min-h-[44px]
        transition-colors duration-150
        focus-ring
        ${sizeClasses[size]}
        ${variantClasses[variant]}
        ${className}
      `}
      {...rest}
    >
      <Icon name={icon} size={size === 'lg' ? 'md' : 'sm'} filled={filled} />
    </button>
  );
}
