interface BadgeProps {
  variant?: 'default' | 'success' | 'warning' | 'error' | 'muted';
  children: React.ReactNode;
  className?: string;
}

const variants = {
  default:  'bg-[#1a1917] text-white',
  success:  'bg-[#f0fdf4] text-[#15803d] border border-[#bbf7d0]',
  warning:  'bg-[#fffbeb] text-[#b45309] border border-[#fde68a]',
  error:    'bg-[#fef2f2] text-[#b91c1c] border border-[#fecaca]',
  muted:    'bg-[#f0eeea] text-[#6b6762] border border-[#dedad4]',
};

export function Badge({ variant = 'default', children, className = '' }: BadgeProps) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${variants[variant]} ${className}`}>
      {children}
    </span>
  );
}
