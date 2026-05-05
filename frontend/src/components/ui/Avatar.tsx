interface AvatarProps {
  name?: string;
  src?: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const sizes = {
  sm: 'h-7 w-7 text-xs',
  md: 'h-8 w-8 text-sm',
  lg: 'h-10 w-10 text-base',
};

function getInitials(name?: string): string {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/);
  return parts.length === 1
    ? parts[0][0].toUpperCase()
    : (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function Avatar({ name, src, size = 'md', className = '' }: AvatarProps) {
  if (src) {
    return (
      <img
        src={src}
        alt={name ?? 'User'}
        className={`rounded-full object-cover ${sizes[size]} ${className}`}
      />
    );
  }
  return (
    <div
      className={`rounded-full bg-[#1a1917] text-white flex items-center justify-center font-semibold flex-shrink-0 ${sizes[size]} ${className}`}
      title={name}
    >
      {getInitials(name)}
    </div>
  );
}
