'use client';

import { useState } from 'react';
import { Icon } from '@/components/ui/Icon';

interface AIChatInputProps {
  onSend: (message: string) => void;
  loading?: boolean;
  placeholder?: string;
  className?: string;
}

export function AIChatInput({ onSend, loading = false, placeholder = 'Ask anything about this resource…', className = '' }: AIChatInputProps) {
  const [value, setValue] = useState('');

  const handleSend = () => {
    const msg = value.trim();
    if (!msg || loading) return;
    onSend(msg);
    setValue('');
  };

  return (
    <div className={`flex items-end gap-2 ${className}`}>
      <div className="flex-1 relative">
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleSend()}
          placeholder={placeholder}
          className="
            w-full h-12 px-4 pr-12 rounded-2xl
            border border-[var(--border-base)]
            bg-[var(--bg-sunken)]
            text-sm text-[var(--text-primary)]
            placeholder:text-[var(--text-tertiary)]
            focus:outline-none focus:border-[var(--color-primary)]
            transition-colors
          "
          disabled={loading}
        />
      </div>
      <button
        onClick={handleSend}
        disabled={!value.trim() || loading}
        className="
          flex-shrink-0
          w-12 h-12 rounded-2xl
          bg-[var(--color-purple)] text-white
          flex items-center justify-center
          hover:opacity-90 transition-opacity
          disabled:opacity-40 disabled:cursor-not-allowed
          shadow-sm
        "
        aria-label="Send message"
      >
        {loading ? (
          <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
        ) : (
          <Icon name="send" size="sm" />
        )}
      </button>
    </div>
  );
}
