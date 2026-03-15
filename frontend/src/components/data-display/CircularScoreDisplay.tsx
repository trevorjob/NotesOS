interface CircularScoreDisplayProps {
  score: number;
  size?: 'md' | 'lg';
  label?: string;
  className?: string;
}

function getScoreColor(score: number): string {
  if (score >= 85) return 'var(--color-success)';
  if (score >= 60) return 'var(--color-warning)';
  return 'var(--color-error)';
}

export function CircularScoreDisplay({
  score,
  size = 'lg',
  label = 'Score',
  className = '',
}: CircularScoreDisplayProps) {
  const normalized = Math.min(100, Math.max(0, score));
  const r = size === 'lg' ? 52 : 36;
  const cx = size === 'lg' ? 60 : 44;
  const strokeWidth = size === 'lg' ? 7 : 5;
  const circumference = 2 * Math.PI * r;
  const dash = (normalized / 100) * circumference;
  const color = getScoreColor(normalized);
  const dim = cx * 2;

  return (
    <div className={`relative inline-flex items-center justify-center ${className}`}>
      <svg
        width={dim}
        height={dim}
        viewBox={`0 0 ${dim} ${dim}`}
        role="img"
        aria-label={`Score: ${normalized}%`}
      >
        {/* Track */}
        <circle
          cx={cx}
          cy={cx}
          r={r}
          fill="none"
          stroke="var(--border-base)"
          strokeWidth={strokeWidth}
        />
        {/* Score arc */}
        <circle
          cx={cx}
          cy={cx}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeDasharray={`${dash} ${circumference}`}
          strokeLinecap="round"
          transform={`rotate(-90 ${cx} ${cx})`}
          style={{ transition: 'stroke-dasharray 1s ease-out' }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span
          className="font-display font-bold leading-none"
          style={{
            fontSize: size === 'lg' ? '2rem' : '1.4rem',
            color,
          }}
        >
          {normalized}%
        </span>
        {label && (
          <span className="text-[10px] uppercase tracking-wider text-[var(--text-tertiary)] mt-0.5">
            {label}
          </span>
        )}
      </div>
    </div>
  );
}
