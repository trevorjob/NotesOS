import { useKnowledgeStore } from '@/stores/knowledge';
import { Collapsible } from '@/components/ui/Collapsible';

interface ConceptsProps {
  topicId: string;
}

export function Concepts({ topicId }: ConceptsProps) {
  const knowledge = useKnowledgeStore((s) => s.topicKnowledge[topicId]);

  const concepts = knowledge?.concepts ?? [];

  if (knowledge?.status !== 'completed' || concepts.length === 0) return null;

  return (
    <Collapsible title="Concepts" count={concepts.length} storageKey={`concepts-${topicId}`}>
      <dl className="space-y-3">
        {concepts.map((c, i) => (
          <div key={i}>
            <dt className="text-sm font-semibold text-[#1a1917]">{c.term}</dt>
            <dd className="text-sm text-[#6b6762] mt-0.5">{c.definition}</dd>
          </div>
        ))}
      </dl>
    </Collapsible>
  );
}
