/**
 * NotesOS - Knowledge Store
 * Caches TopicKnowledge and AudioLesson per topic with polling support
 */

import { create } from 'zustand';
import { api } from '@/lib/api';

export type KnowledgeStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface TopicKnowledge {
  id: string;
  topic_id: string;
  consolidated_note: string | null;
  key_points: string[];
  concepts: Array<{ term: string; definition: string }>;
  source_count: number;
  status: KnowledgeStatus;
  error_message: string | null;
  generated_at: string | null;
}

export interface AudioLesson {
  id: string;
  topic_id: string;
  audio_url: string | null;
  duration_seconds: number | null;
  status: KnowledgeStatus;
  voice: string;
  error_message: string | null;
}

interface KnowledgeState {
  topicKnowledge: Record<string, TopicKnowledge>;
  topicAudio: Record<string, AudioLesson>;
  isLoadingKnowledge: Record<string, boolean>;
  isLoadingAudio: Record<string, boolean>;

  fetchKnowledge: (topicId: string) => Promise<void>;
  forceRefetchKnowledge: (topicId: string) => Promise<void>;
  fetchAudio: (topicId: string) => Promise<void>;
  triggerRegenerate: (topicId: string) => Promise<void>;
  triggerRegenerateAudio: (topicId: string) => Promise<void>;
  startPollingKnowledge: (topicId: string, prevGeneratedAt?: string | null) => () => void;
  startPollingAudio: (topicId: string) => () => void;
}

export const useKnowledgeStore = create<KnowledgeState>()((set, get) => ({
  topicKnowledge: {},
  topicAudio: {},
  isLoadingKnowledge: {},
  isLoadingAudio: {},

  fetchKnowledge: async (topicId) => {
    const existing = get().topicKnowledge[topicId];
    // Skip if already loaded and stable (not mid-processing)
    if (existing && existing.status !== 'processing' && existing.status !== 'pending') return;
    if (get().isLoadingKnowledge[topicId]) return;
    set((s) => ({ isLoadingKnowledge: { ...s.isLoadingKnowledge, [topicId]: true } }));
    try {
      const res = await api.knowledge.get(topicId);
      set((s) => ({
        topicKnowledge: { ...s.topicKnowledge, [topicId]: res.data },
        isLoadingKnowledge: { ...s.isLoadingKnowledge, [topicId]: false },
      }));
    } catch {
      set((s) => ({ isLoadingKnowledge: { ...s.isLoadingKnowledge, [topicId]: false } }));
    }
  },

  forceRefetchKnowledge: async (topicId) => {
    try {
      const res = await api.knowledge.get(topicId);
      set((s) => ({
        topicKnowledge: { ...s.topicKnowledge, [topicId]: res.data },
      }));
    } catch { /* ignore */ }
  },

  fetchAudio: async (topicId) => {
    const existing = get().topicAudio[topicId];
    // Skip if we already have a stable audio URL
    if (existing && existing.status !== 'processing' && existing.status !== 'pending') return;
    if (get().isLoadingAudio[topicId]) return;
    set((s) => ({ isLoadingAudio: { ...s.isLoadingAudio, [topicId]: true } }));
    try {
      const res = await api.knowledge.getAudio(topicId);
      set((s) => ({
        topicAudio: { ...s.topicAudio, [topicId]: res.data },
        isLoadingAudio: { ...s.isLoadingAudio, [topicId]: false },
      }));
    } catch {
      set((s) => ({ isLoadingAudio: { ...s.isLoadingAudio, [topicId]: false } }));
    }
  },

  triggerRegenerate: async (topicId) => {
    await api.knowledge.regenerate(topicId);
    // Optimistically mark as processing
    set((s) => ({
      topicKnowledge: {
        ...s.topicKnowledge,
        [topicId]: { ...(s.topicKnowledge[topicId] ?? {}), status: 'processing' } as TopicKnowledge,
      },
    }));
  },

  triggerRegenerateAudio: async (topicId) => {
    await api.knowledge.regenerateAudio(topicId);
    set((s) => ({
      topicAudio: {
        ...s.topicAudio,
        [topicId]: { ...(s.topicAudio[topicId] ?? {}), status: 'processing' } as AudioLesson,
      },
    }));
  },

  startPollingKnowledge: (topicId, prevGeneratedAt?) => {
    // When prevGeneratedAt is provided (re-upload case): only stop when we see a
    // completed/failed record whose generated_at differs from the one we recorded
    // before the upload. Avoids clock-skew issues with timestamp comparisons.
    const isChanged = (generatedAt: string | null) => {
      if (prevGeneratedAt === undefined) return true; // no tracking — stop on any stable status
      return generatedAt !== prevGeneratedAt;
    };

    const interval = setInterval(async () => {
      try {
        const res = await api.knowledge.get(topicId);
        set((s) => ({
          topicKnowledge: { ...s.topicKnowledge, [topicId]: res.data },
        }));
        const stable = res.data.status === 'completed' || res.data.status === 'failed';
        if (stable && isChanged(res.data.generated_at)) {
          clearInterval(interval);
        }
      } catch {
        clearInterval(interval);
      }
    }, 3000);
    return () => clearInterval(interval);
  },

  startPollingAudio: (topicId) => {
    const interval = setInterval(async () => {
      const current = get().topicAudio[topicId];
      if (current?.status === 'completed' || current?.status === 'failed') {
        clearInterval(interval);
        return;
      }
      try {
        const res = await api.knowledge.getAudio(topicId);
        set((s) => ({
          topicAudio: { ...s.topicAudio, [topicId]: res.data },
        }));
        if (res.data.status === 'completed' || res.data.status === 'failed') {
          clearInterval(interval);
        }
      } catch {
        clearInterval(interval);
      }
    }, 3000);
    return () => clearInterval(interval);
  },
}));
