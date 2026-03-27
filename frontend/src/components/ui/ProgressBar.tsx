interface ProgressBarProps {
  value: number; // 0–100
  size?: 'sm' | 'md';
  className?: string;
  showLabel?: boolean;
}

export function ProgressBar({ value, size = 'sm', className = '', showLabel = false }: ProgressBarProps) {
  const clamped = Math.max(0, Math.min(100, value));
  const h = size === 'sm' ? 'h-1.5' : 'h-2.5';

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <div className={`flex-1 bg-[#e8e5e0] rounded-full overflow-hidden ${h}`}>
        <div
          className={`${h} bg-[#1a1917] rounded-full transition-all duration-500`}
          style={{ width: `${clamped}%` }}
        />
      </div>
      {showLabel && (
        <span className="text-xs text-[#6b6762] w-9 text-right">{Math.round(clamped)}%</span>
      )}
    </div>
  );
}
