'use client';

interface ImmersiveLayoutProps {
  children: React.ReactNode;
  topBar?: React.ReactNode;
  footerBar?: React.ReactNode;
}

export function ImmersiveLayout({ children, topBar, footerBar }: ImmersiveLayoutProps) {
  return (
    <div className="min-h-screen bg-[var(--bg-base)] flex flex-col">
      {topBar}

      <main
        className="
          flex-1
          pt-[60px]
          pb-[env(safe-area-inset-bottom)]
          overflow-auto
        "
      >
        {children}
      </main>

      {footerBar && (
        <footer
          className="
            fixed bottom-0 left-0 right-0 z-40
            pb-[env(safe-area-inset-bottom)]
            bg-[var(--bg-elevated)]
            border-t border-[var(--border-base)]
          "
        >
          {footerBar}
        </footer>
      )}
    </div>
  );
}
