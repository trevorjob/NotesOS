import { Icon } from '@/components/ui/Icon';

interface MetricCardProps {
  icon: string;
  value: string | number;
  label: string;
  growth?: string;
  growthPositive?: boolean;
  iconFilled?: boolean;
  className?: string;
}

export function MetricCard({
  icon,
  value,
  label,
  growth,
  growthPositive = true,
  iconFilled = false,
  className = '',
}: MetricCardProps) {
  return (
    <div className={`glass-card p-5 flex flex-col gap-3 ${className}`}>
      <div className="w-10 h-10 rounded-xl bg-[var(--color-primary-muted)] flex items-center justify-center">
        <Icon name={icon} size="sm" className="text-[var(--color-primary)]" filled={iconFilled} />
      </div>
      <div>
        <p className="text-2xl font-display font-bold text-[var(--text-primary)] leading-none mb-1">
          {value}
        </p>
        <p className="text-xs text-[var(--text-secondary)] font-medium">{label}</p>
      </div>
      {growth && (
        <div className={`flex items-center gap-1 text-xs font-semibold ${growthPositive ? 'text-[var(--color-success)]' : 'text-[var(--color-error)]'}`}>
          <Icon name={growthPositive ? 'trending_up' : 'trending_down'} size="xs" />
          {growth}
        </div>
      )}
    </div>
  );
}
