/**
 * NotesOS - Progress Store
 * Streak, course/topic progress, recommendations, session tracking
 */

import { create } from 'zustand';
import { api } from '@/lib/api';

export interface TopicProgress {
    topic_id: string;
    mastery_level: number;
    total_study_time: number;
    avg_score: number | null;
    streak_days: number;
    last_activity: string;
}

export interface CourseProgress {
    course_id: string;
    overall_mastery: number;
    total_study_time: number;
    current_streak: number;
    topics_count: number;
    topics_mastered: number;
}

export interface Recommendation {
    topic_id: string;
    reason: string;
    priority: string;
    type: string;
}

interface ProgressState {
    streak: number;
    courseProgress: CourseProgress | null;
    topicsProgress: TopicProgress[];
    recommendations: Recommendation[];
    activeSessionId: string | null;
    isLoading: boolean;
    error: string | null;

    fetchStreak: (courseId: string) => Promise<void>;
    fetchCourseProgress: (courseId: string) => Promise<void>;
    fetchTopicsProgress: (courseId: string) => Promise<void>;
    fetchRecommendations: (courseId: string) => Promise<void>;
    startSession: (topicId: string, sessionType: 'reading' | 'quiz' | 'practice') => Promise<string>;
    endSession: (sessionId: string) => Promise<void>;
    clearCourseProgress: () => void;
    clearError: () => void;
}

export const useProgressStore = create<ProgressState>()((set, get) => ({
    streak: 0,
    courseProgress: null,
    topicsProgress: [],
    recommendations: [],
    activeSessionId: null,
    isLoading: false,
    error: null,

    fetchStreak: async (courseId: string) => {
        try {
            const response = await api.progress.getStreak(courseId);
            set({ streak: response.data.current_streak ?? 0 });
        } catch {
            set({ streak: 0 });
        }
    },

    fetchCourseProgress: async (courseId: string) => {
        set({ isLoading: true, error: null });
        try {
            const response = await api.progress.getCourseProgress(courseId);
            set({ courseProgress: response.data, isLoading: false });
        } catch (err: unknown) {
            const message = err && typeof err === 'object' && 'response' in err
                ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
                : 'Failed to load progress';
            set({ isLoading: false, error: String(message) });
        }
    },

    fetchTopicsProgress: async (courseId: string) => {
        try {
            const response = await api.progress.getTopicsProgress(courseId);
            set({ topicsProgress: response.data ?? [] });
        } catch {
            set({ topicsProgress: [] });
        }
    },

    fetchRecommendations: async (courseId: string) => {
        try {
            const response = await api.progress.getRecommendations(courseId);
            set({ recommendations: response.data ?? [] });
        } catch {
            set({ recommendations: [] });
        }
    },

    startSession: async (topicId: string, sessionType: 'reading' | 'quiz' | 'practice') => {
        const response = await api.progress.startSession({ topic_id: topicId, session_type: sessionType });
        const sessionId = response.data.session_id;
        set({ activeSessionId: sessionId });
        return sessionId;
    },

    endSession: async (sessionId: string) => {
        await api.progress.endSession(sessionId);
        set({ activeSessionId: get().activeSessionId === sessionId ? null : get().activeSessionId });
    },

    clearCourseProgress: () => set({
        courseProgress: null,
        topicsProgress: [],
        recommendations: [],
        streak: 0,
    }),

    clearError: () => set({ error: null }),
}));
