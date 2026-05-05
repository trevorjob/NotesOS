import { TextareaHTMLAttributes, forwardRef } from 'react';

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, error, className = '', id, ...props }, ref) => {
    const inputId = id ?? label?.toLowerCase().replace(/\s+/g, '-');
    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label htmlFor={inputId} className="text-sm text-[#1a1917] font-serif">
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          id={inputId}
          className={`
            min-h-[100px] px-3 py-2.5 rounded-lg border font-serif text-sm text-[#1a1917]
            bg-[#f0eeea] border-[#dedad4] placeholder:text-[#c4bfb9] resize-y
            focus:outline-none focus:border-[#1a1917] transition-colors duration-150
            disabled:opacity-50 disabled:cursor-not-allowed
            ${error ? 'border-red-500' : ''}
            ${className}
          `}
          {...props}
        />
        {error && <p className="text-xs text-red-600">{error}</p>}
      </div>
    );
  }
);

Textarea.displayName = 'Textarea';
