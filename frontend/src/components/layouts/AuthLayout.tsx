import Link from 'next/link';

interface AuthLayoutProps {
  children: React.ReactNode;
}

export function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="min-h-screen bg-[var(--bg-base)] flex flex-col items-center justify-center px-4 py-12">
      {/* Logo */}
      <Link href="/" className="flex items-center gap-2 mb-10" aria-label="NoteOS home">
        <div className="w-9 h-9 rounded-xl bg-[var(--color-primary)] flex items-center justify-center shadow-md">
          <span className="font-display font-bold text-white text-base">N</span>
        </div>
        <span className="font-display font-semibold text-xl text-[var(--text-primary)]">NoteOS</span>
      </Link>

      {/* Card */}
      <div className="w-full max-w-[420px]">
        {children}
      </div>

      {/* Footer */}
      <p className="mt-8 text-xs text-[var(--text-tertiary)] text-center">
        © {new Date().getFullYear()} NoteOS — Study smarter, together.
      </p>
    </div>
  );
}
