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
        <div className="flex items-center gap-3 bg-[#f0f9ff] border border-[#bae6fd] rounded-xl px-4 py-3">
          <span className="h-4 w-4 rounded-full border-2 border-[#0284c7] border-t-transparent animate-spin shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-[#0c4a6e]">Processing your materials…</p>
            <p className="text-xs text-[#0369a1] mt-0.5">
              We&apos;re reading your files, generating notes and key concepts. This usually takes 1–3 minutes.
            </p>
          </div>
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
