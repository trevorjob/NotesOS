'use client';

interface ToggleSwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  description?: string;
  disabled?: boolean;
  id?: string;
}

export function ToggleSwitch({
  checked,
  onChange,
  label,
  description,
  disabled = false,
  id,
}: ToggleSwitchProps) {
  const switchId = id ?? `toggle-${Math.random().toString(36).slice(2, 8)}`;

  return (
    <label
      htmlFor={switchId}
      className={`flex items-center justify-between gap-4 cursor-pointer ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
    >
      <div className="flex-1 min-w-0">
        <span className="text-sm font-medium text-[var(--text-primary)] block">{label}</span>
        {description && (
          <span className="text-xs text-[var(--text-secondary)] block mt-0.5">{description}</span>
        )}
      </div>
      <div className="relative flex-shrink-0">
        <input
          type="checkbox"
          id={switchId}
          checked={checked}
          onChange={(e) => !disabled && onChange(e.target.checked)}
          disabled={disabled}
          className="sr-only"
        />
        <div
          className={`
            w-11 h-6 rounded-full transition-colors duration-200
            ${checked ? 'bg-[var(--color-primary)]' : 'bg-[var(--border-base)]'}
          `}
        >
          <div
            className={`
              absolute top-0.5 left-0.5
              w-5 h-5 rounded-full bg-white shadow-sm
              transition-transform duration-200
              ${checked ? 'translate-x-5' : 'translate-x-0'}
            `}
          />
        </div>
      </div>
    </label>
  );
}
