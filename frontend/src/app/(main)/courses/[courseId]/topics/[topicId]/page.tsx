'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useCourseStore } from '@/stores/courses';
import { useResourcesStore } from '@/stores/resources';
import { useProgressStore } from '@/stores/progress';
import { useNetworkStore } from '@/stores/network';
import { AIPreClassResearchCard } from '@/components/ai/AIPreClassResearchCard';
import { ResourceCard } from '@/components/cards/ResourceCard';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Skeleton } from '@/components/feedback/Skeleton';
import { FAB } from '@/components/ui/FAB';
import { TabBar } from '@/components/ui/TabBar';
import { Icon } from '@/components/ui/Icon';
import { LinearProgressBar } from '@/components/data-display/LinearProgressBar';
import { useToast } from '@/components/feedback/ToastProvider';
import { FileUpload } from '@/components/FileUpload';
import { AIChatOverlay } from '@/components/AIChatOverlay';
import { MarkdownRenderer } from '@/components/MarkdownRenderer';
import { useAIChatStore } from '@/stores/aiChat';
import { connectWebSocket, WebSocketClient, WebSocketMessage } from '@/lib/websocket';
import { api } from '@/lib/api';

const UPLOAD_TABS = [{ id: 'files', label: 'Upload Files' }, { id: 'text', label: 'Write Notes' }];

export default function TopicDetailPage() {
  const { courseId, topicId } = useParams<{ courseId: string; topicId: string }>();
  const router = useRouter();
  const toast = useToast();

  const { currentCourse } = useCourseStore();
  const { isOnline } = useNetworkStore();
  const { resources, isLoading: resLoading, isUploading, uploadProgress, fetchResources, createTextResource, uploadFiles, deleteResource } = useResourcesStore();
  const { messages, isSending, fetchConversations, askQuestion, clearCurrentConversation } = useAIChatStore();
  const { startSession, endSession } = useProgressStore();

  const [topic, setTopic]                 = useState<any>(null);
  const [research, setResearch]           = useState<any>(null);
  const [researchLoading, setResLoading]  = useState(false);
  const [generating, setGenerating]       = useState(false);
  const [uploadTab, setUploadTab]         = useState('files');
  const [textTitle, setTextTitle]         = useState('');
  const [textContent, setTextContent]     = useState('');
  const [savingText, setSavingText]       = useState(false);

  const sessionRef = useRef<string | null>(null);
  const wsRef = useRef<WebSocketClient | null>(null);
  const fetchedRef = useRef(false);

  useEffect(() => {
    if (fetchedRef.current) return;
    fetchedRef.current = true;
    api.topics.getById(topicId).then((r) => setTopic(r.data)).catch(() => {});
  }, [topicId]);

  useEffect(() => { fetchResources(topicId); }, [topicId, fetchResources]);

  useEffect(() => {
    if (!courseId) return;
    fetchConversations(courseId);
    return () => clearCurrentConversation();
  }, [courseId, fetchConversations, clearCurrentConversation]);

  useEffect(() => {
    setResLoading(true);
    api.ai.getResearch(topicId).then((r) => setResearch(r.data)).catch(() => {}).finally(() => setResLoading(false));
  }, [topicId]);

  useEffect(() => {
    startSession(topicId, 'reading').then((id) => { sessionRef.current = id; });
    return () => {
      if (sessionRef.current) endSession(sessionRef.current);
      sessionRef.current = null;
    };
  }, [topicId, startSession, endSession]);

  useEffect(() => {
    if (!courseId) return;
    const { updateResourceProcessingStatus } = useResourcesStore.getState();
    const client = connectWebSocket(courseId, {
      onMessage: (msg: WebSocketMessage) => {
        if (msg.type === 'processing_status') updateResourceProcessingStatus(msg.resource_id, msg.status);
        if (msg.type === 'resource_created' || msg.type === 'resource_updated' || msg.type === 'resource_deleted') fetchResources(topicId);
      },
      onOpen: () => {},
      onClose: () => {},
      onError: () => {},
    });
    wsRef.current = client;
    return () => { client.disconnect(); wsRef.current = null; };
  }, [courseId, topicId, fetchResources]);

  const handleGenerateResearch = async () => {
    setGenerating(true);
    try {
      const r = await api.ai.generateResearch(topicId);
      setResearch(r.data);
      toast.success('Research generated!');
    } catch {
      toast.error('Failed to generate research.');
    } finally {
      setGenerating(false);
    }
  };

  const handleUpload = async (files: File[], title?: string, isHandwritten?: boolean) => {
    await uploadFiles(topicId, courseId, files, title, isHandwritten);
  };

  const handleSaveText = async () => {
    if (!textContent.trim()) return;
    setSavingText(true);
    try {
      await createTextResource(topicId, { title: textTitle || undefined, content: textContent });
      setTextTitle(''); setTextContent(''); setUploadTab('files');
      toast.success('Notes saved!');
    } catch {
      toast.error('Failed to save notes.');
    } finally {
      setSavingText(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteResource(id);
      toast.success('Resource deleted.');
    } catch {
      toast.error('Failed to delete.');
    }
  };

  const completionPct = topic?.completion_percentage ?? 0;

  if (!topic) {
    return (
      <div className="px-4 md:px-8 py-6 max-w-3xl mx-auto">
        <Skeleton className="h-7 w-48 mb-2" variant="text" />
        <Skeleton className="h-4 w-64 mb-6" variant="text" />
        <Skeleton className="h-40 mb-4" />
        <Skeleton className="h-32 mb-4" />
      </div>
    );
  }

  return (
    <div className="px-4 md:px-8 py-6 max-w-3xl mx-auto">
      {/* Breadcrumb */}
      <button
        onClick={() => router.push(`/courses/${courseId}`)}
        className="flex items-center gap-1.5 text-xs uppercase tracking-wider font-bold text-[var(--color-primary)] hover:underline mb-4"
      >
        <Icon name="arrow_back" size="xs" /> {currentCourse?.code ?? 'Course'}
      </button>

      {/* Topic header */}
      <h1 className="font-display font-bold text-2xl text-[var(--text-primary)] mb-1">
        {topic.title}
      </h1>
      {topic.week_number && (
        <p className="text-xs uppercase tracking-wider text-[var(--text-tertiary)] mb-3">
          Week {topic.week_number}
        </p>
      )}
      <LinearProgressBar value={completionPct} showLabel className="max-w-xs mb-8" />

      {/* AI Pre-Class Research */}
      <AIPreClassResearchCard
        summary={research?.research_content ? research.research_content.slice(0, 300) + (research.research_content.length > 300 ? '…' : '') : null}
        loading={researchLoading}
        onGenerate={handleGenerateResearch}
        generating={generating}
        className="mb-8"
      />

      {/* Resources */}
      <section>
        <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--text-tertiary)] mb-4">
          Study Resources
        </h2>

        {/* Upload area (online only) */}
        {isOnline && (
          <div className="mb-6">
            <TabBar tabs={UPLOAD_TABS} active={uploadTab} onChange={setUploadTab} variant="pill" className="mb-4" />
            {uploadTab === 'files' ? (
              <FileUpload onUpload={handleUpload} isUploading={isUploading} uploadProgress={uploadProgress} />
            ) : (
              <div className="flex flex-col gap-3">
                <input
                  type="text"
                  placeholder="Title (optional)"
                  value={textTitle}
                  onChange={(e) => setTextTitle(e.target.value)}
                  className="w-full h-10 px-4 rounded-xl border border-[var(--border-base)] bg-[var(--bg-sunken)] text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:border-[var(--color-primary)]"
                />
                <textarea
                  placeholder="Write your notes here… (supports Markdown)"
                  value={textContent}
                  onChange={(e) => setTextContent(e.target.value)}
                  rows={6}
                  className="w-full p-4 rounded-xl border border-[var(--border-base)] bg-[var(--bg-sunken)] text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:border-[var(--color-primary)] font-mono resize-none"
                />
                <button
                  onClick={handleSaveText}
                  disabled={!textContent.trim() || savingText}
                  className="self-end h-10 px-5 rounded-xl bg-[var(--color-primary)] text-white text-sm font-semibold disabled:opacity-50"
                >
                  {savingText ? 'Saving…' : 'Save Notes'}
                </button>
              </div>
            )}
          </div>
        )}

        {resLoading ? (
          <div className="flex flex-col gap-3">
            {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-16" />)}
          </div>
        ) : resources.length === 0 ? (
          <EmptyState icon="description" title="No resources yet" body="Upload your notes, PDFs, or images to get started." />
        ) : (
          <div className="flex flex-col gap-3">
            {resources.map((r: any) => (
              <ResourceCard
                key={r.id}
                id={r.id}
                topicId={topicId}
                courseId={courseId}
                title={r.title ?? 'Untitled'}
                type={r.resource_type ?? 'other'}
                isVerified={r.is_verified}
              />
            ))}
          </div>
        )}
      </section>

      {/* AI Chat overlay */}
      <AIChatOverlay
        messages={messages}
        onSendMessage={(q) => askQuestion(courseId, q, topicId)}
        isLoading={isSending}
        courseId={courseId}
      />
    </div>
  );
}
