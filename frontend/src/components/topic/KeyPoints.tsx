import { useKnowledgeStore } from '@/stores/knowledge';
import { Collapsible } from '@/components/ui/Collapsible';

interface KeyPointsProps {
  topicId: string;
}

export function KeyPoints({ topicId }: KeyPointsProps) {
  const knowledge = useKnowledgeStore((s) => s.topicKnowledge[topicId]);

  const points = knowledge?.key_points ?? [];

  if (knowledge?.status !== 'completed' || points.length === 0) return null;

  return (
    <Collapsible title="Key Points" count={points.length} defaultOpen storageKey={`kp-${topicId}`}>
      <ul className="space-y-1.5">
        {points.map((p, i) => (
          <li key={i} className="flex items-start gap-2 text-sm text-[#1a1917]">
            <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-[#1a1917] shrink-0" />
            {p}
          </li>
        ))}
      </ul>
    </Collapsible>
  );
}
