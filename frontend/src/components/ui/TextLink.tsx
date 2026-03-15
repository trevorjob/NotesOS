import Link from 'next/link';

type TextLinkVariant = 'standard' | 'editorial';

interface TextLinkProps {
  href: string;
  children: React.ReactNode;
  variant?: TextLinkVariant;
  external?: boolean;
  className?: string;
}

export function TextLink({
  href,
  children,
  variant = 'standard',
  external = false,
  className = '',
}: TextLinkProps) {
  const base = `
    transition-colors duration-150
    focus-ring rounded-sm
    ${variant === 'editorial'
      ? 'text-[var(--color-primary)] font-display italic underline underline-offset-4 decoration-[var(--color-primary-muted)] hover:decoration-[var(--color-primary)]'
      : 'text-[var(--color-primary)] hover:underline underline-offset-2 text-sm font-medium'
    }
    ${className}
  `;

  if (external) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className={base}>
        {children}
      </a>
    );
  }

  return (
    <Link href={href} className={base}>
      {children}
    </Link>
  );
}
