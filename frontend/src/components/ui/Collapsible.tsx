'use client';

import { useState, useEffect } from 'react';

interface CollapsibleProps {
  title: string;
  count?: number;
  defaultOpen?: boolean;
  storageKey?: string;
  children: React.ReactNode;
}

export function Collapsible({
  title,
  count,
  defaultOpen = false,
  storageKey,
  children,
}: CollapsibleProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  // Persist open state per topic in localStorage
  useEffect(() => {
    if (!storageKey) return;
    const saved = localStorage.getItem(storageKey);
    if (saved !== null) setIsOpen(saved === 'true');
  }, [storageKey]);

  const toggle = () => {
    const next = !isOpen;
    setIsOpen(next);
    if (storageKey) localStorage.setItem(storageKey, String(next));
  };

  return (
    <div className="border border-[#dedad4] rounded-lg overflow-hidden">
      <button
        onClick={toggle}
        className="w-full flex items-center justify-between px-4 py-3 bg-white hover:bg-[#f9f8f6] transition-colors text-left"
        aria-expanded={isOpen}
      >
        <span className="text-sm font-semibold text-[#1a1917]">
          {title}
          {count !== undefined && (
            <span className="ml-2 text-[#9e9a94] font-normal">{count}</span>
          )}
        </span>
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          className={`text-[#9e9a94] transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
        >
          <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </button>

      {isOpen && (
        <div className="px-4 py-3 bg-white border-t border-[#dedad4] animate-fade-in">
          {children}
        </div>
      )}
    </div>
  );
}
