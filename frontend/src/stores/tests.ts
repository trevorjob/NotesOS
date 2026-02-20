/**
 * NotesOS - Tests Store
 * Generate tests, submit answers (text/voice), fetch results
 */

import { create } from 'zustand';
import { api } from '@/lib/api';

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
    submitAnswers: (testId: string, answers: Array<{ question_id: string; answer_text: string }>) => Promise<string>;
    submitVoiceAnswer: (testId: string, questionId: string, audioFile: File, attemptId?: string) => Promise<string>;
    getTestResults: (attemptId: string) => Promise<TestResults>;
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

    submitAnswers: async (testId, answers) => {
        set({ isSubmitting: true, error: null });
        try {
            const response = await api.ai.submitAnswers(testId, answers.map((a) => ({
                question_id: a.question_id,
                answer_text: a.answer_text,
            })));
            const attemptId = response.data.answer_id;
            set({ lastAttemptId: attemptId, isSubmitting: false });
            return attemptId;
        } catch (err: unknown) {
            const message = err && typeof err === 'object' && 'response' in err
                ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
                : 'Failed to submit';
            set({ isSubmitting: false, error: String(message) });
            throw new Error(String(message));
        }
    },

    submitVoiceAnswer: async (testId, questionId, audioFile, attemptId) => {
        set({ isSubmitting: true, error: null });
        try {
            const response = await api.ai.submitVoiceAnswer(testId, questionId, audioFile, attemptId);
            const data = response.data as { answer_id: string; attempt_id?: string };
            const newAttemptId = data.attempt_id ?? data.answer_id;
            set((s) => ({ lastAttemptId: newAttemptId || s.lastAttemptId, isSubmitting: false }));
            return newAttemptId;
        } catch (err: unknown) {
            const message = err && typeof err === 'object' && 'response' in err
                ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
                : 'Failed to submit voice answer';
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

    clearTest: () => set({ currentTest: null, lastAttemptId: null, results: null }),
    clearError: () => set({ error: null }),
}));
