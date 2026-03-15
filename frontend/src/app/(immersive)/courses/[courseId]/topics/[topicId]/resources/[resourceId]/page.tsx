'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ImmersiveLayout } from '@/components/layouts/ImmersiveLayout';
import { ReadingTopBar } from '@/components/layouts/TopBar';
import { ReadingProgressBar } from '@/components/data-display/ReadingProgressBar';
import { GlassFloatingPanel } from '@/components/ai/GlassFloatingPanel';
import { AIChatInput } from '@/components/ai/AIChatInput';
import { AIContextCard } from '@/components/ai/AIContextCard';
import { Skeleton } from '@/components/feedback/Skeleton';
import { MarkdownRenderer } from '@/components/MarkdownRenderer';
import { useAIChatStore } from '@/stores/aiChat';
import { api } from '@/lib/api';

export default function ResourceDetailPage() {
  const { courseId, topicId, resourceId } = useParams<{ courseId: string; topicId: string; resourceId: string }>();
  const router = useRouter();

  const [resource, setResource] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [isDark, setIsDark] = useState(false);
  const { messages, isSending, askQuestion } = useAIChatStore();

  useEffect(() => {
    api.resources.getById(resourceId)
      .then((r) => setResource(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [resourceId]);

  const toggleTheme = () => {
    setIsDark((v) => {
      document.documentElement.classList.toggle('dark', !v);
      return !v;
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen pt-[60px] px-4 max-w-3xl mx-auto py-8">
        <Skeleton className="h-7 w-64 mb-6" variant="text" />
        {[...Array(6)].map((_, i) => <Skeleton key={i} className="h-4 mb-3" variant="text" />)}
      </div>
    );
  }

  return (
    <ImmersiveLayout
      topBar={
        <ReadingTopBar
          title={resource?.title ?? 'Resource'}
          onExit={() => router.back()}
          onToggleTheme={toggleTheme}
          isDark={isDark}
        />
      }
    >
      <ReadingProgressBar />

      <div className="flex lg:gap-6 max-w-6xl mx-auto">
        {/* Reading content */}
        <main className="flex-1 px-4 md:px-8 py-8 max-w-3xl">
          <article className="prose-reading">
            {resource?.processed_content ? (
              <MarkdownRenderer content={resource.processed_content} />
            ) : resource?.content ? (
              <MarkdownRenderer content={resource.content} />
            ) : (
              <p className="text-[var(--text-secondary)]">No content available for this resource.</p>
            )}
          </article>
        </main>

        {/* AI Panel */}
        <aside className="lg:flex-shrink-0">
          <GlassFloatingPanel title="AI Assistant" defaultOpen={false}>
            {/* AI context cards */}
            {resource?.ai_summary && (
              <AIContextCard type="analysis" content={resource.ai_summary} />
            )}

            {/* Chat history */}
            <div className="flex flex-col gap-3 flex-1">
              {messages.map((msg: any, i: number) => (
                <div
                  key={i}
                  className={`p-3 rounded-xl text-sm ${
                    msg.role === 'user'
                      ? 'bg-[var(--color-primary-muted)] text-[var(--text-primary)] self-end ml-4'
                      : 'bg-[var(--bg-sunken)] text-[var(--text-secondary)] mr-4'
                  }`}
                >
                  {msg.content}
                </div>
              ))}
            </div>

            <AIChatInput
              onSend={(q) => askQuestion(courseId, q, topicId)}
              loading={isSending}
              placeholder="Ask about this resource…"
            />
          </GlassFloatingPanel>
        </aside>
      </div>
    </ImmersiveLayout>
  );
}
