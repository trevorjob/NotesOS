import { useKnowledgeStore } from '@/stores/knowledge';
import { MarkdownRenderer } from '@/components/ui/MarkdownRenderer';
import { Spinner } from '@/components/ui/Spinner';

interface ConsolidatedNoteProps {
  topicId: string;
}

export function ConsolidatedNote({ topicId }: ConsolidatedNoteProps) {
  const knowledge = useKnowledgeStore((s) => s.topicKnowledge[topicId]);
  const isLoading = useKnowledgeStore((s) => s.isLoadingKnowledge[topicId]);

  if (isLoading && !knowledge) {
    return (
      <div className="flex items-center gap-2 py-6 text-[#6b6762]">
        <Spinner size="sm" />
        <span className="text-sm">Loading notes…</span>
      </div>
    );
  }

  if (!knowledge || knowledge.status === 'pending') {
    return (
      <div className="py-6">
        <p className="text-sm text-[#9e9a94]">No materials yet — upload resources to generate notes.</p>
      </div>
    );
  }

  if (knowledge.status === 'processing') {
    return (
      <div className="flex items-center gap-2 py-6 text-[#6b6762]">
        <Spinner size="sm" />
        <span className="text-sm">Synthesising notes from your materials…</span>
      </div>
    );
  }

  if (knowledge.status === 'failed') {
    return (
      <div className="py-4 text-sm text-[#dc2626]">
        Failed to generate notes. Try regenerating from the menu.
      </div>
    );
  }

  if (!knowledge.consolidated_note) {
    return (
      <div className="py-6">
        <p className="text-sm text-[#9e9a94]">Notes not available yet.</p>
      </div>
    );
  }

  return <MarkdownRenderer content={knowledge.consolidated_note} />;
}
