/**
 * NotesOS - Tests Store
 * Generate tests, submit answers (text/voice), fetch results
 */

import { create } from 'zustand';
import { api } from '@/lib/api';
import { WebSocketClient } from '@/lib/websocket';

export interface TestQuestion {
    id: string;
    question_text: string;
    question_type: string;
    answer_options: string[] | null;
    points: number;
    order_index: number;
}

export interface Test {
    id: string;
    title: string;
    question_count: number;
    questions: TestQuestion[];
}

export interface GradedAnswer {
    score: number;
    feedback: string;
    encouragement: string;
    key_points_covered: string[];
    key_points_missed: string[];
}

export interface TestResults {
    attempt_id: string;
    total_score: number;
    max_score: number;
    completed_at: string | null;
    answers: GradedAnswer[];
}

interface TestsState {
    currentTest: Test | null;
    lastAttemptId: string | null;
    results: TestResults | null;
    isGenerating: boolean;
    isSubmitting: boolean;
    error: string | null;

    generateTest: (courseId: string, topicIds: string[], questionCount: number, difficulty?: string, questionTypes?: string[]) => Promise<Test>;
    getTest: (testId: string) => Promise<Test>;
    /** Single-request submission for text AND voice answers. */
    submitFull: (
        testId: string,
        answers: Array<{ question_id: string; answer_text: string; is_voice?: boolean }>,
        voiceFiles?: Record<string, File>,
    ) => Promise<string>;
    getTestResults: (attemptId: string) => Promise<TestResults>;
    /**
     * Open a WebSocket for a course and wait for grading:complete with a matching attemptId.
     * Fetches results and calls onComplete once grading finishes.
     * Cleans up automatically on completion or after a 5-minute timeout.
     */
    listenForGrading: (attemptId: string, courseId: string, onComplete: (results: TestResults) => void) => () => void;
    clearTest: () => void;
    clearError: () => void;
}

export const useTestsStore = create<TestsState>()((set, get) => ({
    currentTest: null,
    lastAttemptId: null,
    results: null,
    isGenerating: false,
    isSubmitting: false,
    error: null,

    generateTest: async (courseId, topicIds, questionCount, difficulty = 'medium', questionTypes?: string[]) => {
        set({ isGenerating: true, error: null });
        try {
            const types = questionTypes?.length ? questionTypes : ['mcq', 'short_answer'];
            const response = await api.ai.generateTest(courseId, {
                topic_ids: topicIds,
                question_count: questionCount,
                difficulty,
                question_types: types,
            });
            const test = response.data;
            set({ currentTest: test, isGenerating: false });
            return test;
        } catch (err: unknown) {
            const message = err && typeof err === 'object' && 'response' in err
                ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
                : 'Failed to generate test';
            set({ isGenerating: false, error: String(message) });
            throw new Error(String(message));
        }
    },

    getTest: async (testId) => {
        const response = await api.ai.getTest(testId);
        const test = response.data;
        set({ currentTest: test });
        return test;
    },

    submitFull: async (testId, answers, voiceFiles) => {
        set({ isSubmitting: true, error: null });
        try {
            const response = await api.ai.submitFull(testId, answers, voiceFiles);
            const attemptId: string = response.data.attempt_id;
            set({ lastAttemptId: attemptId, isSubmitting: false });
            return attemptId;
        } catch (err: unknown) {
            const message = err && typeof err === 'object' && 'response' in err
                ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
                : 'Failed to submit answers';
            set({ isSubmitting: false, error: String(message) });
            throw new Error(String(message));
        }
    },

    getTestResults: async (attemptId) => {
        const response = await api.ai.getTestResults(attemptId);
        const results = response.data;
        set({ results });
        return results;
    },

    listenForGrading: (attemptId, courseId, onComplete) => {
        const ws = new WebSocketClient(courseId, {
            onMessage: async (message) => {
                if (message.type === 'grading:complete' && message.attempt_id === attemptId) {
                    clearTimeout(timeout);
                    ws.disconnect();
                    try {
                        const response = await api.ai.getTestResults(attemptId);
                        const results: TestResults = response.data;
                        set({ results });
                        onComplete(results);
                    } catch {
                        // Best-effort — page will show what's available
                    }
                }
            },
        });
        ws.connect();

        // Safety timeout: disconnect after 5 minutes if grading never completes
        const timeout = setTimeout(() => {
            ws.disconnect();
        }, 5 * 60 * 1000);

        // Return cleanup function for useEffect
        return () => {
            clearTimeout(timeout);
            ws.disconnect();
        };
    },

    clearTest: () => set({ currentTest: null, lastAttemptId: null, results: null }),
    clearError: () => set({ error: null }),
}));
