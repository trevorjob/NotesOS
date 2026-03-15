'use client';

import { useState } from 'react';
import { Icon } from '@/components/ui/Icon';

interface GlassFloatingPanelProps {
  title?: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
  className?: string;
}

export function GlassFloatingPanel({
  title = 'AI Assistant',
  children,
  defaultOpen = false,
  className = '',
}: GlassFloatingPanelProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <>
      {/* Mobile: Floating toggle button */}
      <button
        className="
          lg:hidden
          fixed bottom-[calc(env(safe-area-inset-bottom)+80px)] right-4
          w-14 h-14 rounded-2xl
          bg-[var(--color-purple)] text-white
          flex items-center justify-center
          shadow-lg
          z-30
        "
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? 'Close AI panel' : 'Open AI panel'}
      >
        <Icon name="auto_awesome" size="md" />
      </button>

      {/* Panel */}
      <div
        className={`
          ${open ? 'translate-x-0' : 'translate-x-full lg:translate-x-0'}
          transition-transform duration-300 ease-in-out
          fixed right-0 top-[60px] bottom-0 z-20
          lg:relative lg:top-auto lg:bottom-auto lg:z-auto
          w-80 lg:w-72
          glass-panel
          flex flex-col
          ${className}
        `}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--glass-border)]">
          <div className="flex items-center gap-2">
            <Icon name="auto_awesome" size="xs" className="text-[var(--color-purple)]" />
            <span className="text-sm font-semibold text-[var(--text-primary)]">{title}</span>
          </div>
          <button
            onClick={() => setOpen(false)}
            className="lg:hidden min-w-[32px] min-h-[32px] flex items-center justify-center text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
            aria-label="Close panel"
          >
            <Icon name="close" size="xs" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">
          {children}
        </div>
      </div>
    </>
  );
}
