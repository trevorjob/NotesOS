import { Icon } from '@/components/ui/Icon';
import { Button } from '@/components/ui/Button';

interface EmptyStateProps {
  icon?: string;
  title: string;
  body?: string;
  ctaLabel?: string;
  onCta?: () => void;
  className?: string;
}

export function EmptyState({ icon, title, body, ctaLabel, onCta, className = '' }: EmptyStateProps) {
  return (
    <div className={`flex flex-col items-center justify-center text-center px-6 py-16 ${className}`}>
      {icon && (
        <div className="w-16 h-16 rounded-2xl bg-[var(--bg-sunken)] flex items-center justify-center mb-5">
          <Icon name={icon} size="lg" className="text-[var(--text-tertiary)]" />
        </div>
      )}
      <h3 className="font-display font-semibold text-xl text-[var(--text-primary)] mb-2">
        {title}
      </h3>
      {body && (
        <p className="text-sm text-[var(--text-secondary)] max-w-[300px] leading-relaxed mb-6">
          {body}
        </p>
      )}
      {ctaLabel && onCta && (
        <Button onClick={onCta} variant="primary" size="md">
          {ctaLabel}
        </Button>
      )}
    </div>
  );
}
