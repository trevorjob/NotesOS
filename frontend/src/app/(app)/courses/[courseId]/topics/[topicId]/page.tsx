'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useCourseStore } from '@/stores/courses';
import { useKnowledgeStore } from '@/stores/knowledge';
import { useProgressStore } from '@/stores/progress';
import { api } from '@/lib/api';

import { AudioPlayer } from '@/components/topic/AudioPlayer';
import { ConsolidatedNote } from '@/components/topic/ConsolidatedNote';
import { KeyPoints } from '@/components/topic/KeyPoints';
import { Concepts } from '@/components/topic/Concepts';
import { Sources, type Resource } from '@/components/topic/Sources';
import { AIChatPanel } from '@/components/topic/AIChatPanel';
import { FocusMode } from '@/components/topic/FocusMode';
import { AddResourcesModal } from '@/components/topic/AddResourcesModal';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';

interface TopicDetail {
  id: string;
  title: string;
  description?: string;
  course_id: string;
  knowledge_status?: string;
  audio_status?: string;
  has_audio?: boolean;
}

export default function TopicPage() {
  const params = useParams<{ courseId: string; topicId: string }>();
  const { courseId, topicId } = params;
  const router = useRouter();

  const selectCourse = useCourseStore((s) => s.selectCourse);
  const courses = useCourseStore((s) => s.courses);
  const { fetchKnowledge, fetchAudio, startPollingKnowledge, startPollingAudio } = useKnowledgeStore();
  const knowledge = useKnowledgeStore((s) => s.topicKnowledge[topicId]);
  const audio = useKnowledgeStore((s) => s.topicAudio[topicId]);

  const [topic, setTopic] = useState<TopicDetail | null>(null);
  const [loadingTopic, setLoadingTopic] = useState(true);

  // Resources — lifted to avoid re-fetch on FocusMode toggle
  const [resources, setResources] = useState<Resource[]>([]);
  const resourcesFetched = useRef(false);

  const [showChat, setShowChat] = useState(false);
  const [focusMode, setFocusMode] = useState(false);
  const [showUpload, setShowUpload] = useState(false);

  // ── Data fetching ───────────────────────────────────────────────────────

  const fetchResources = useCallback(async () => {
    try {
      const res = await api.resources.getByTopic(topicId);
      setResources(res.data?.resources ?? res.data ?? []);
    } catch { /* ignore */ }
  }, [topicId]);

  useEffect(() => {
    if (!topicId) return;

    // Load topic detail + siblings (for focus mode prev/next)
    setLoadingTopic(true);
    api.topics.getById(topicId)
      .then((res) => setTopic(res.data?.topic ?? res.data))
      .finally(() => setLoadingTopic(false));

    // Load course with topics (for focus mode prev/next + sidebar accuracy)
    selectCourse(courseId);

    // Load knowledge & audio
    fetchKnowledge(topicId);

    // Only fetch audio if topic indicates one may exist
    // We'll fetch after topic loads to check has_audio
  }, [topicId, courseId, selectCourse, fetchKnowledge]);

  // Fetch audio only if the topic has one or audio is already in store
  useEffect(() => {
    if (!topic) return;
    if (topic.has_audio || topic.audio_status === 'completed' || topic.audio_status === 'processing') {
      fetchAudio(topicId);
    }
  }, [topic, topicId, fetchAudio]);

  // Fetch resources once per topic
  useEffect(() => {
    resourcesFetched.current = false;
  }, [topicId]);

  useEffect(() => {
    if (!resourcesFetched.current) {
      resourcesFetched.current = true;
      fetchResources();
    }
  }, [fetchResources]);

  // Poll knowledge while processing
  useEffect(() => {
    if (knowledge?.status === 'processing') {
      return startPollingKnowledge(topicId);
    }
  }, [knowledge?.status, topicId, startPollingKnowledge]);

  // Poll audio while processing — only if we know audio exists
  useEffect(() => {
    if (audio?.status === 'processing' || audio?.status === 'pending') {
      return startPollingAudio(topicId);
    }
  }, [audio?.status, topicId, startPollingAudio]);

  // F key toggles focus mode
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.key === 'f' || e.key === 'F') &&
        document.activeElement?.tagName !== 'INPUT' &&
        document.activeElement?.tagName !== 'TEXTAREA') {
        setFocusMode((v) => !v);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  // Save last visited topic + update recents list
  useEffect(() => {
    if (topicId && courseId) {
      try {
        localStorage.setItem('last_topic_id', topicId);
        localStorage.setItem('last_course_id', courseId);
        const key = 'notesos-recent-topics';
        const existing: Array<{ topicId: string; courseId: string }> =
          JSON.parse(localStorage.getItem(key) ?? '[]');
        const filtered = existing.filter((e) => e.topicId !== topicId);
        localStorage.setItem(key, JSON.stringify([{ topicId, courseId }, ...filtered].slice(0, 5)));
      } catch { /* ignore */ }
    }
  }, [topicId, courseId]);

  // Auto start/end reading session (silent background tracking)
  useEffect(() => {
    const { startSession, endSession } = useProgressStore.getState();
    let sessionId: string | null = null;
    startSession(topicId, 'reading').then((id) => { sessionId = id; }).catch(() => {});
    return () => {
      if (sessionId) endSession(sessionId).catch(() => {});
    };
  }, [topicId]);

  // ── Derived: prev/next topics ────────────────────────────────────────────

  const course = courses.find((c) => c.id === courseId);
  const siblings = course?.topics ?? [];
  const currentIdx = siblings.findIndex((t) => t.id === topicId);
  const prevTopic = currentIdx > 0 ? siblings[currentIdx - 1] : null;
  const nextTopic = currentIdx >= 0 && currentIdx < siblings.length - 1 ? siblings[currentIdx + 1] : null;

  // ── Render ──────────────────────────────────────────────────────────────

  if (loadingTopic) {
    return <div className="flex items-center justify-center h-64"><Spinner size="lg" /></div>;
  }

  if (!topic) {
    return <div className="flex items-center justify-center h-64"><p className="text-[#6b6762]">Topic not found.</p></div>;
  }

  const showAudioPlayer = !!(topic.has_audio || audio?.audio_url || audio?.status === 'processing');

  const mainContent = (
    <div className="max-w-3xl mx-auto px-4 md:px-6 py-8 space-y-6">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-1.5 text-xs text-[#9e9a94] flex-wrap">
        <Link href="/home" className="hover:text-[#1a1917] transition-colors">Home</Link>
        <span>/</span>
        <span className="text-[#6b6762]">{course?.code ?? courseId}</span>
        <span>/</span>
        <span className="text-[#1a1917] font-medium truncate">{topic.title}</span>
      </nav>

      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <h1 className="text-2xl font-semibold text-[#1a1917] leading-tight">{topic.title}</h1>
        <div className="flex items-center gap-2 shrink-0">
          <Button variant="ghost" size="sm" onClick={() => setShowUpload(true)}>+ Add</Button>
          <Button variant="ghost" size="sm" onClick={() => setFocusMode(true)}>Focus</Button>
        </div>
      </div>

      {/* Audio player */}
      {showAudioPlayer && <AudioPlayer topicId={topicId} />}

      {/* Knowledge sections */}
      <KeyPoints topicId={topicId} />
      <ConsolidatedNote topicId={topicId} />
      <Concepts topicId={topicId} />

      {/* Quiz me */}
      {knowledge?.status === 'completed' && (
        <div className="pt-2">
          <Button onClick={() => router.push(`/courses/${courseId}/topics/${topicId}/quiz`)}>
            ❓ Quiz me
          </Button>
        </div>
      )}

      {/* Sources */}
      <Sources resources={resources} />

      {/* Empty state when no resources */}
      {resources.length === 0 && (
        <div className="bg-white rounded-xl border border-[#dedad4] px-6 py-8 text-center">
          <p className="text-sm text-[#6b6762] mb-3">No materials uploaded yet.</p>
          <Button size="sm" onClick={() => setShowUpload(true)}>+ Add Materials</Button>
        </div>
      )}
    </div>
  );

  return (
    <>
      {focusMode ? (
        <FocusMode
          onExit={() => setFocusMode(false)}
          prevTopicHref={prevTopic ? `/courses/${courseId}/topics/${prevTopic.id}` : undefined}
          nextTopicHref={nextTopic ? `/courses/${courseId}/topics/${nextTopic.id}` : undefined}
        >
          {mainContent}
        </FocusMode>
      ) : mainContent}

      {/* Floating Ask AI */}
      {!showChat && (
        <button
          onClick={() => setShowChat(true)}
          className="fixed bottom-6 right-6 flex items-center gap-2 bg-[#1a1917] text-white px-4 py-2.5 rounded-full shadow-lg hover:opacity-90 transition-opacity text-sm font-medium z-30"
        >
          💬 Ask AI
        </button>
      )}

      {/* AI Chat panel */}
      {showChat && (
        <AIChatPanel topicId={topicId} courseId={courseId} onClose={() => setShowChat(false)} />
      )}

      {/* Add Resources modal */}
      <AddResourcesModal
        isOpen={showUpload}
        topicId={topicId}
        courseId={courseId}
        onClose={() => setShowUpload(false)}
        onAdded={() => {
          resourcesFetched.current = false;
          fetchResources();
        }}
      />
    </>
  );
}
