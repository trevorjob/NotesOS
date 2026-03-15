import { Icon } from '@/components/ui/Icon';

type AIContextType = 'analysis' | 'vocabulary' | 'question';

interface AIContextCardProps {
  type: AIContextType;
  content: string;
  className?: string;
}

const typeConfig: Record<AIContextType, { icon: string; label: string; accent: string }> = {
  analysis:   { icon: 'analytics',    label: 'Analysis',   accent: 'text-[var(--color-primary)]' },
  vocabulary: { icon: 'menu_book',    label: 'Vocabulary', accent: 'text-[var(--color-info)]' },
  question:   { icon: 'help_outline', label: 'Insight',    accent: 'text-[var(--color-purple)]' },
};

export function AIContextCard({ type, content, className = '' }: AIContextCardProps) {
  const cfg = typeConfig[type];

  return (
    <div className={`glass-card p-4 ${className}`}>
      <div className={`flex items-center gap-1.5 mb-2 text-xs font-bold uppercase tracking-wider ${cfg.accent}`}>
        <Icon name={cfg.icon} size="xs" />
        {cfg.label}
      </div>
      <p className="text-sm text-[var(--text-secondary)] leading-relaxed">{content}</p>
    </div>
  );
}
