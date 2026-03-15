interface SkeletonProps {
  className?: string;
  variant?: 'text' | 'rect' | 'circle';
  width?: string;
  height?: string;
}

export function Skeleton({ className = '', variant = 'rect', width, height }: SkeletonProps) {
  const shape =
    variant === 'circle' ? 'rounded-full' :
    variant === 'text'   ? 'rounded-sm' :
    'rounded-lg';

  return (
    <div
      className={`animate-pulse bg-[var(--border-base)] ${shape} ${className}`}
      style={{ width, height }}
      aria-hidden="true"
    />
  );
}

export function SkeletonCard({ className = '' }: { className?: string }) {
  return (
    <div className={`glass-card p-5 space-y-3 ${className}`}>
      <Skeleton variant="text" className="h-4 w-2/3" />
      <Skeleton variant="text" className="h-3 w-full" />
      <Skeleton variant="text" className="h-3 w-4/5" />
      <Skeleton className="h-1.5 w-full mt-4" />
    </div>
  );
}
