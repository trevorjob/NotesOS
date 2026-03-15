import { Icon } from '@/components/ui/Icon';

type MiniStatType = 'progress' | 'due' | 'action';

interface MiniStatCardProps {
  type: MiniStatType;
  icon: string;
  value: string | number;
  label: string;
  onClick?: () => void;
  className?: string;
}

const typeClasses: Record<MiniStatType, string> = {
  progress: 'border-[var(--color-primary-muted)] bg-[var(--color-primary-soft)]',
  due:      'border-[var(--warning-bg)] bg-[var(--warning-bg)]',
  action:   'border-[var(--border-base)] bg-[var(--bg-elevated)]',
};

const iconClasses: Record<MiniStatType, string> = {
  progress: 'text-[var(--color-primary)]',
  due:      'text-[var(--color-warning)]',
  action:   'text-[var(--text-secondary)]',
};

export function MiniStatCard({
  type,
  icon,
  value,
  label,
  onClick,
  className = '',
}: MiniStatCardProps) {
  const Tag = onClick ? 'button' : 'div';

  return (
    <Tag
      {...(onClick ? { onClick, type: 'button' } : {})}
      className={`
        flex items-center gap-3 p-4 rounded-xl
        border transition-all duration-150
        ${typeClasses[type]}
        ${onClick ? 'cursor-pointer hover:opacity-80' : ''}
        ${className}
      `}
    >
      <Icon name={icon} size="sm" className={iconClasses[type]} />
      <div>
        <p className="text-lg font-display font-bold text-[var(--text-primary)] leading-none">{value}</p>
        <p className="text-xs text-[var(--text-secondary)] mt-0.5">{label}</p>
      </div>
    </Tag>
  );
}
