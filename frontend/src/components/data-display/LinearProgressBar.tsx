type ProgressColor = 'primary' | 'white' | 'muted' | 'success' | 'warning' | 'error';
type ProgressSize = 'thin' | 'default';

interface LinearProgressBarProps {
  value: number;
  max?: number;
  color?: ProgressColor;
  size?: ProgressSize;
  showLabel?: boolean;
  className?: string;
}

const colorClasses: Record<ProgressColor, string> = {
  primary: 'bg-[var(--color-primary)]',
  white:   'bg-white',
  muted:   'bg-[var(--text-tertiary)]',
  success: 'bg-[var(--color-success)]',
  warning: 'bg-[var(--color-warning)]',
  error:   'bg-[var(--color-error)]',
};

export function LinearProgressBar({
  value,
  max = 100,
  color = 'primary',
  size = 'default',
  showLabel = false,
  className = '',
}: LinearProgressBarProps) {
  const pct = Math.round(Math.min(100, Math.max(0, (value / max) * 100)));

  return (
    <div className={`w-full ${className}`}>
      {showLabel && (
        <div className="flex justify-between mb-1">
          <span className="text-xs text-[var(--text-secondary)]">Progress</span>
          <span className="text-xs font-semibold text-[var(--color-primary)]">{pct}%</span>
        </div>
      )}
      <div
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        className={`w-full bg-[var(--border-base)] rounded-full overflow-hidden ${size === 'thin' ? 'h-0.5' : 'h-1.5'}`}
      >
        <div
          className={`h-full rounded-full transition-all duration-500 ease-out ${colorClasses[color]}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
