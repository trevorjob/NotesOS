'use client';

import { useCallback, useEffect, useReducer, useRef, useState } from 'react';
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
import { topicsBeingPrepared } from '@/components/topic/CreateTopicModal';
import { topicDetailCache, resourceCache } from '@/lib/topicCache';
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

// Focus mode persists across topic navigation — only cleared by explicit user action.
// Use an object so the property is mutable while the binding stays const.
const _focusModeState = { active: false };

export default function TopicPage() {
  const params = useParams<{ courseId: string; topicId: string }>();
  const { courseId, topicId } = params;
  const router = useRouter();

  const selectCourse = useCourseStore((s) => s.selectCourse);
  const courses = useCourseStore((s) => s.courses);
  const { fetchKnowledge, fetchAudio, startPollingKnowledge, startPollingAudio } = useKnowledgeStore();
  const knowledge = useKnowledgeStore((s) => s.topicKnowledge[topicId]);
  const audio = useKnowledgeStore((s) => s.topicAudio[topicId]);

  // Re-render trigger — called after writing new data into a module-level cache.
  // This avoids synchronous setState calls inside effects.
  const [, bump] = useReducer((n: number) => n + 1, 0);

  // Read directly from module-level caches (populated on first visit, persisted across navigations).
  const cachedDetail = topicDetailCache.get(topicId) ?? null;
  const cachedResources = resourceCache.get(topicId) ?? null;

  // Sidebar stub — available immediately from the courses store (no API needed)
  const course = courses.find((c) => c.id === courseId);
  const storeTopicStub = course?.topics?.find((t) => t.id === topicId);

  // Compose topic: full API detail > store stub (enough to render instantly)
  const topic: TopicDetail | null =
    cachedDetail ??
    (storeTopicStub
      ? { id: storeTopicStub.id, title: storeTopicStub.title, course_id: courseId }
      : null);

  // Only show the full-screen spinner when we have absolutely nothing
  const loadingTopic = !topic;

  // Resources from cache; fall back to empty array while loading
  const resources: Resource[] = cachedResources ?? [];

  const resourcesFetched = useRef(resourceCache.has(topicId));

  const [showChat, setShowChat] = useState(false);
  const [focusMode, setFocusModeRender] = useState(_focusModeState.active);
  const [showUpload, setShowUpload] = useState(false);

  const setFocusMode = useCallback((v: boolean) => {
    _focusModeState.active = v;
    setFocusModeRender(v);
  }, []);

  // Initialise to true when this topic was just created with resources (module-level signal from CreateTopicModal)
  const [processingResources, setProcessingResources] = useState(() => {
    if (topicsBeingPrepared.has(topicId)) {
      topicsBeingPrepared.delete(topicId);
      return true;
    }
    return false;
  });

  // ── Data fetching ───────────────────────────────────────────────────────

  const fetchResources = useCallback(async () => {
    try {
      const res = await api.resources.getByTopic(topicId);
      const data: Resource[] = res.data?.resources ?? res.data ?? [];
      resourceCache.set(topicId, data);
      bump();
    } catch { /* ignore */ }
  }, [topicId, bump]);

  useEffect(() => {
    if (!topicId) return;

    // Reset the resources-fetched gate for this topic
    resourcesFetched.current = resourceCache.has(topicId);

    // Fetch full topic detail if not already cached; bump to re-render when done
    if (!topicDetailCache.has(topicId)) {
      api.topics.getById(topicId)
        .then((res) => {
          topicDetailCache.set(topicId, res.data?.topic ?? res.data);
          bump();
        })
        .catch(() => {});
    }

    // Load course with topics (for sidebar + prev/next)
    selectCourse(courseId);

    // Load knowledge (store skips automatically if already cached)
    fetchKnowledge(topicId);
  }, [topicId, courseId, selectCourse, fetchKnowledge, bump]);

  // Fetch audio — always attempt so we don't miss it when the topic stub lacks has_audio
  useEffect(() => {
    fetchAudio(topicId);
  }, [topicId, fetchAudio]);

  // Fetch resources if not already cached
  useEffect(() => {
    if (!resourcesFetched.current) {
      resourcesFetched.current = true;
      fetchResources();
    }
  }, [fetchResources]);

  // Poll knowledge while processing/pending — also kick off immediately for freshly created topics.
  // processingResources stays true until knowledge is done; we derive the banner separately.
  useEffect(() => {
    const needsPoll = knowledge?.status === 'processing'
      || knowledge?.status === 'pending'
      || (processingResources && knowledge?.status !== 'completed' && knowledge?.status !== 'failed');
    if (needsPoll) {
      return startPollingKnowledge(topicId);
    }
  }, [knowledge?.status, processingResources, topicId, startPollingKnowledge]);

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
        setFocusMode(!_focusModeState.active);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [setFocusMode]);

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
    let cancelled = false;
    const { startSession, endSession } = useProgressStore.getState();
    let sessionId: string | null = null;
    startSession(topicId, 'reading')
      .then((id) => {
        if (cancelled) { endSession(id).catch(() => {}); }
        else { sessionId = id; }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
      if (sessionId) endSession(sessionId).catch(() => {});
    };
  }, [topicId]);

  // ── Derived: prev/next topics ────────────────────────────────────────────

  const siblings = course?.topics ?? [];
  const currentIdx = siblings.findIndex((t) => t.id === topicId);
  const prevTopic = currentIdx > 0 ? siblings[currentIdx - 1] : null;
  const nextTopic = currentIdx >= 0 && currentIdx < siblings.length - 1 ? siblings[currentIdx + 1] : null;

  // Warm caches for a sibling topic on hover — so clicking feels instant
  function prefetchTopic(tid: string) {
    if (!topicDetailCache.has(tid)) {
      api.topics.getById(tid)
        .then((res) => topicDetailCache.set(tid, res.data?.topic ?? res.data))
        .catch(() => {});
    }
    if (!resourceCache.has(tid)) {
      api.resources.getByTopic(tid)
        .then((res) => resourceCache.set(tid, res.data?.resources ?? res.data ?? []))
        .catch(() => {});
    }
    // Knowledge store already skips if cached
    fetchKnowledge(tid);
  }

  // ── Render ──────────────────────────────────────────────────────────────

  if (loadingTopic) {
    return <div className="flex items-center justify-center h-64"><Spinner size="lg" /></div>;
  }

  if (!topic) {
    return <div className="flex items-center justify-center h-64"><p className="text-[#6b6762]">Topic not found.</p></div>;
  }

  const showAudioPlayer = !!(topic.has_audio || audio?.audio_url || audio?.status === 'processing');

  const mainContent = (
    <div className={`px-4 md:px-6 py-8 space-y-6 max-w-3xl mx-auto transition-all duration-300 ${showChat ? 'md:mr-[38%]' : ''}`}>
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

      {/* Processing banner — shown while workers are running or materials are freshly uploaded */}
      {((processingResources && knowledge?.status !== 'completed' && knowledge?.status !== 'failed')
        || knowledge?.status === 'processing'
        || knowledge?.status === 'pending') && (
        <div className="flex items-center gap-3 bg-[#f0f9ff] border border-[#bae6fd] rounded-xl px-4 py-3">
          <span className="h-4 w-4 rounded-full border-2 border-[#0284c7] border-t-transparent animate-spin shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-[#0c4a6e]">Processing your materials…</p>
            <p className="text-xs text-[#0369a1] mt-0.5">
              We&apos;re reading your files, generating notes and key concepts. This usually takes 1–3 minutes.
            </p>
          </div>
        </div>
      )}

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

      {/* Empty state — hide while materials are being prepared/processed */}
      {resources.length === 0
        && !(processingResources && knowledge?.status !== 'completed' && knowledge?.status !== 'failed')
        && knowledge?.status !== 'processing'
        && knowledge?.status !== 'pending'
        && (
        <div className="bg-white rounded-xl border border-[#dedad4] px-6 py-8 text-center">
          <p className="text-sm text-[#6b6762] mb-3">No materials uploaded yet.</p>
          <Button size="sm" onClick={() => setShowUpload(true)}>+ Add Materials</Button>
        </div>
      )}

      {/* Prev / Next topic navigation */}
      {(prevTopic || nextTopic) && (
        <div className="flex items-center justify-between pt-4 border-t border-[#dedad4]">
          {prevTopic ? (
            <Link
              href={`/courses/${courseId}/topics/${prevTopic.id}`}
              prefetch
              onMouseEnter={() => prefetchTopic(prevTopic.id)}
              className="group flex items-center gap-2 text-sm text-[#6b6762] hover:text-[#1a1917] transition-colors"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M10 3L5 8l5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
              <span className="truncate max-w-[180px]">{prevTopic.title}</span>
            </Link>
          ) : <div />}
          {nextTopic ? (
            <Link
              href={`/courses/${courseId}/topics/${nextTopic.id}`}
              prefetch
              onMouseEnter={() => prefetchTopic(nextTopic.id)}
              className="group flex items-center gap-2 text-sm text-[#6b6762] hover:text-[#1a1917] transition-colors"
            >
              <span className="truncate max-w-[180px]">{nextTopic.title}</span>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M6 3l5 5-5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </Link>
          ) : <div />}
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
          setProcessingResources(true);
          resourceCache.delete(topicId); // invalidate cache so fresh data loads
          resourcesFetched.current = false;
          fetchResources();
          // Start polling immediately so we catch when the workers kick off
          startPollingKnowledge(topicId);
        }}
      />
    </>
  );
}
