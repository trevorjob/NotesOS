'use client';

interface IconProps {
  name: string;
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl';
  filled?: boolean;
  className?: string;
}

const sizeMap = {
  xs: 'text-base',    // 16px
  sm: 'text-xl',      // 20px
  md: 'text-2xl',     // 24px
  lg: 'text-3xl',     // 30px
  xl: 'text-4xl',     // 36px
};

export function Icon({ name, size = 'md', filled = false, className = '' }: IconProps) {
  const cls = filled ? 'material-symbols-filled' : 'material-symbols-outlined';
  return (
    <span
      className={`${cls} ${sizeMap[size]} select-none leading-none ${className}`}
      aria-hidden="true"
    >
      {name}
    </span>
  );
}
