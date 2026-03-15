type BadgeVariant = 'success' | 'warning' | 'error' | 'info' | 'neutral' | 'primary';

interface StatusBadgeProps {
  variant?: BadgeVariant;
  label: string;
  pulse?: boolean;
  size?: 'sm' | 'md';
  className?: string;
}

const variantClasses: Record<BadgeVariant, string> = {
  success: 'bg-[var(--success-bg)] text-[var(--success-text)]',
  warning: 'bg-[var(--warning-bg)] text-[var(--warning-text)]',
  error:   'bg-[var(--error-bg)]   text-[var(--error-text)]',
  info:    'bg-[var(--info-bg)]    text-[var(--info-text)]',
  neutral: 'bg-[var(--neutral-bg)] text-[var(--neutral-text)]',
  primary: 'bg-[var(--color-primary-muted)] text-[var(--color-primary)]',
};

const dotColors: Record<BadgeVariant, string> = {
  success: 'bg-[var(--color-success)]',
  warning: 'bg-[var(--color-warning)]',
  error:   'bg-[var(--color-error)]',
  info:    'bg-[var(--color-info)]',
  neutral: 'bg-[var(--text-tertiary)]',
  primary: 'bg-[var(--color-primary)]',
};

export function StatusBadge({
  variant = 'neutral',
  label,
  pulse = false,
  size = 'sm',
  className = '',
}: StatusBadgeProps) {
  return (
    <span
      className={`
        inline-flex items-center gap-1.5
        font-semibold uppercase tracking-wider
        rounded-full leading-none
        ${size === 'sm' ? 'text-[10px] px-2 py-1' : 'text-xs px-2.5 py-1.5'}
        ${variantClasses[variant]}
        ${className}
      `}
    >
      {pulse ? (
        <span className="relative flex w-1.5 h-1.5">
          <span className={`absolute inline-flex h-full w-full rounded-full opacity-75 animate-ping ${dotColors[variant]}`} />
          <span className={`relative inline-flex rounded-full w-1.5 h-1.5 ${dotColors[variant]}`} />
        </span>
      ) : null}
      {label}
    </span>
  );
}
