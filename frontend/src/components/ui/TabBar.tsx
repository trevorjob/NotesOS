'use client';

import { useRef } from 'react';

export interface Tab {
  id: string;
  label: string;
  icon?: string;
}

type TabBarVariant = 'underline' | 'pill';

interface TabBarProps {
  tabs: Tab[];
  active: string;
  onChange: (id: string) => void;
  variant?: TabBarVariant;
  className?: string;
}

export function TabBar({ tabs, active, onChange, variant = 'underline', className = '' }: TabBarProps) {
  const listRef = useRef<HTMLDivElement>(null);

  const handleKeyDown = (e: React.KeyboardEvent, currentIdx: number) => {
    const len = tabs.length;
    let nextIdx: number | null = null;

    if (e.key === 'ArrowRight') nextIdx = (currentIdx + 1) % len;
    if (e.key === 'ArrowLeft')  nextIdx = (currentIdx - 1 + len) % len;
    if (e.key === 'Home') nextIdx = 0;
    if (e.key === 'End')  nextIdx = len - 1;

    if (nextIdx !== null) {
      e.preventDefault();
      onChange(tabs[nextIdx].id);
      const btn = listRef.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[nextIdx];
      btn?.focus();
    }
  };

  if (variant === 'pill') {
    return (
      <div
        ref={listRef}
        role="tablist"
        className={`flex gap-1 p-1 bg-[var(--bg-sunken)] rounded-xl ${className}`}
      >
        {tabs.map((tab, i) => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={active === tab.id}
            onClick={() => onChange(tab.id)}
            onKeyDown={(e) => handleKeyDown(e, i)}
            className={`
              flex-1 h-9 px-4 rounded-lg text-sm font-semibold
              transition-all duration-150 whitespace-nowrap
              min-h-[44px]
              ${active === tab.id
                ? 'bg-[var(--bg-elevated)] text-[var(--text-primary)] shadow-sm'
                : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
              }
            `}
          >
            {tab.label}
          </button>
        ))}
      </div>
    );
  }

  return (
    <div
      ref={listRef}
      role="tablist"
      className={`flex border-b border-[var(--border-base)] ${className}`}
    >
      {tabs.map((tab, i) => (
        <button
          key={tab.id}
          role="tab"
          aria-selected={active === tab.id}
          onClick={() => onChange(tab.id)}
          onKeyDown={(e) => handleKeyDown(e, i)}
          className={`
            px-5 py-3 text-sm font-semibold
            whitespace-nowrap
            transition-all duration-150
            min-h-[44px]
            border-b-2
            ${active === tab.id
              ? 'text-[var(--color-primary)] border-[var(--color-primary)]'
              : 'text-[var(--text-secondary)] border-transparent hover:text-[var(--text-primary)] hover:border-[var(--border-base)]'
            }
          `}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
