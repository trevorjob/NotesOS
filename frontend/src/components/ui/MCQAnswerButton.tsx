'use client';

interface MCQAnswerButtonProps {
  option: string;
  text: string;
  selected?: boolean;
  correct?: boolean | null;
  disabled?: boolean;
  onClick: () => void;
  className?: string;
}

export function MCQAnswerButton({
  option,
  text,
  selected = false,
  correct = null,
  disabled = false,
  onClick,
  className = '',
}: MCQAnswerButtonProps) {
  const getVariantClasses = () => {
    if (correct === true && selected) {
      return 'border-[var(--color-success)] bg-[var(--success-bg)] text-[var(--success-text)]';
    }
    if (correct === false && selected) {
      return 'border-[var(--color-error)] bg-[var(--error-bg)] text-[var(--error-text)]';
    }
    if (selected) {
      return 'border-[var(--color-primary)] bg-[var(--color-primary-muted)] text-[var(--text-primary)]';
    }
    return 'border-[var(--border-base)] bg-[var(--bg-elevated)] text-[var(--text-primary)] hover:border-[var(--color-primary)] hover:bg-[var(--color-primary-soft)]';
  };

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`
        w-full flex items-start gap-4 p-4 rounded-xl
        border-2 text-left
        transition-all duration-150
        min-h-[56px]
        ${getVariantClasses()}
        ${disabled ? 'cursor-default' : 'cursor-pointer'}
        focus-ring
        ${className}
      `}
    >
      <span className={`
        flex-shrink-0 w-7 h-7 rounded-full
        flex items-center justify-center
        text-sm font-bold leading-none
        border
        ${selected ? 'bg-[var(--color-primary)] border-[var(--color-primary)] text-white' : 'border-current'}
      `}>
        {option}
      </span>
      <span className="flex-1 text-sm leading-snug pt-0.5">{text}</span>
    </button>
  );
}
