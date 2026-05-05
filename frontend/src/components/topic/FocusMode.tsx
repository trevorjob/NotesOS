'use client';

import { useEffect } from 'react';
import Link from 'next/link';

interface FocusModeProps {
  onExit: () => void;
  prevTopicHref?: string;
  nextTopicHref?: string;
  children: React.ReactNode;
}

export function FocusMode({ onExit, prevTopicHref, nextTopicHref, children }: FocusModeProps) {
  // F key or Escape to exit
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'f' || e.key === 'F' || e.key === 'Escape') onExit();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onExit]);

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-[#f0eeea]">
      {/* Exit bar */}
      <div className="sticky top-0 flex items-center justify-between border-b border-[#dedad4] bg-[#f0eeea] px-6 py-3">
        <button
          onClick={onExit}
          className="flex items-center gap-1.5 text-sm text-[#6b6762] transition-colors hover:text-[#1a1917]"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M9 2L4 7l5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Exit focus mode <kbd className="ml-1 rounded bg-[#e8e5e0] px-1 text-xs">F</kbd>
        </button>
      </div>

      {/* Content */}
      <div className="mx-auto max-w-[720px] px-6 py-8">
        {children}
      </div>

      {/* Prev / Next navigation */}
      {/* 
      {(prevTopicHref || nextTopicHref) && (
        <div className="max-w-[720px] mx-auto px-6 pb-12 flex justify-between">
          {prevTopicHref ? (
            <Link
              href={prevTopicHref}
              className="text-sm text-[#6b6762] hover:text-[#1a1917] flex items-center gap-1.5"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M9 2L4 7l5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
              Previous topic
            </Link>
          ) : <span />}
          {nextTopicHref && (
            <Link
              href={nextTopicHref}
              className="text-sm text-[#6b6762] hover:text-[#1a1917] flex items-center gap-1.5"
            >
              Next topic
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M5 2l5 5-5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </Link>
          )}
        </div>
      )} */}
    </div>
  );
}
