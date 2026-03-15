'use client';

interface PillTagProps {
  label: string;
  selected?: boolean;
  onClick?: () => void;
  className?: string;
}

export function PillTag({ label, selected = false, onClick, className = '' }: PillTagProps) {
  const Tag = onClick ? 'button' : 'span';

  return (
    <Tag
      {...(onClick ? { onClick, type: 'button' } : {})}
      className={`
        inline-flex items-center
        px-3 py-1.5
        rounded-full text-sm font-medium
        transition-all duration-150
        select-none
        ${onClick ? 'cursor-pointer' : ''}
        ${selected
          ? 'bg-[var(--color-primary)] text-white shadow-[var(--shadow-primary)]'
          : 'bg-[var(--bg-sunken)] text-[var(--text-secondary)] border border-[var(--border-base)] hover:border-[var(--color-primary)] hover:text-[var(--color-primary)]'
        }
        ${className}
      `}
    >
      {label}
    </Tag>
  );
}
