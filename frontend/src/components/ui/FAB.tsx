import { Icon } from './Icon';

type FABVariant = 'primary' | 'ai';

interface FABProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  icon: string;
  label: string;
  variant?: FABVariant;
  extended?: boolean;
  className?: string;
}

export function FAB({ icon, label, variant = 'primary', extended = false, className = '', ...rest }: FABProps) {
  return (
    <button
      aria-label={label}
      className={`
        fixed bottom-[calc(env(safe-area-inset-bottom)+80px)] right-4
        lg:bottom-8 lg:right-8
        flex items-center justify-center gap-2
        shadow-[var(--shadow-primary)]
        transition-all duration-200
        hover:scale-105 active:scale-95
        focus-ring
        ${extended ? 'h-14 px-5 rounded-2xl text-sm font-semibold' : 'w-14 h-14 rounded-2xl'}
        ${variant === 'ai'
          ? 'bg-[var(--color-purple)] text-white hover:opacity-90'
          : 'bg-[var(--color-primary)] text-white hover:bg-[var(--color-primary-hover)]'
        }
        ${className}
      `}
      {...rest}
    >
      <Icon name={icon} size="md" />
      {extended && <span>{label}</span>}
    </button>
  );
}
