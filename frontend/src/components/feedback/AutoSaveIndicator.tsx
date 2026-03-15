import { Icon } from '@/components/ui/Icon';

type SaveState = 'idle' | 'saving' | 'saved' | 'error';

interface AutoSaveIndicatorProps {
  state: SaveState;
  className?: string;
}

const config: Record<SaveState, { icon: string; label: string; color: string } | null> = {
  idle:   null,
  saving: { icon: 'sync',         label: 'Saving…',  color: 'text-[var(--text-tertiary)]' },
  saved:  { icon: 'check_circle', label: 'Saved',    color: 'text-[var(--color-success)]' },
  error:  { icon: 'error',        label: 'Not saved', color: 'text-[var(--color-error)]' },
};

export function AutoSaveIndicator({ state, className = '' }: AutoSaveIndicatorProps) {
  const cfg = config[state];
  if (!cfg) return null;

  return (
    <span className={`flex items-center gap-1.5 text-xs font-medium ${cfg.color} ${className}`}>
      <Icon name={cfg.icon} size="xs" className={state === 'saving' ? 'animate-spin' : ''} />
      {cfg.label}
    </span>
  );
}
