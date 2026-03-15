import { Icon } from '@/components/ui/Icon';

type StudyStatsVariant = 'compact' | 'recommendation';

interface StudyStatsFeatureCardProps {
  variant?: StudyStatsVariant;
  icon: string;
  title: string;
  subtitle?: string;
  value?: string | number;
  ctaLabel?: string;
  onCta?: () => void;
  className?: string;
}

export function StudyStatsFeatureCard({
  variant = 'compact',
  icon,
  title,
  subtitle,
  value,
  ctaLabel,
  onCta,
  className = '',
}: StudyStatsFeatureCardProps) {
  return (
    <div
      className={`
        glass-card p-4 flex gap-3 items-start
        ${className}
      `}
    >
      <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-[var(--color-primary-muted)] flex items-center justify-center">
        <Icon name={icon} size="xs" className="text-[var(--color-primary)]" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-[var(--text-primary)] leading-snug">{title}</p>
        {subtitle && (
          <p className="text-xs text-[var(--text-secondary)] mt-0.5 leading-snug line-clamp-2">{subtitle}</p>
        )}
        {value !== undefined && (
          <p className="text-lg font-display font-bold text-[var(--color-primary)] mt-1">{value}</p>
        )}
        {ctaLabel && onCta && (
          <button
            onClick={onCta}
            className="mt-2 text-xs font-semibold text-[var(--color-primary)] hover:underline transition-colors"
          >
            {ctaLabel} →
          </button>
        )}
      </div>
    </div>
  );
}
