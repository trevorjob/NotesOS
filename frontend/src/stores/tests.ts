/**
 * NotesOS - Tests Store
 * Generate tests, submit answers (text/voice), fetch results
 */

import { create } from 'zustand';
import { api } from '@/lib/api';
import { WebSocketClient, StreamedQuestion } from '@/lib/websocket';

export interface TestQuestion {
    id: string;
    question_text: string;
    question_type: string;
    answer_options: string[] | null;
    points: number;
    order_index: number;
}

export type TestGenerationStatus = 'pending' | 'generating' | 'ready' | 'failed';

export interface Test {
    id: string;
    title: string;
    question_count: number;
    questions: TestQuestion[];
    generation_status: TestGenerationStatus;
    batches_done: number;
    batches_total: number | null;
    failure_reason?: string | null;
}

export interface GradedAnswer {
    question_id: string;
    question_text: string;
    user_answer: string;
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

    generateTest: (courseId: string, topicIds: string[], questionCount: number, difficulty?: string, questionTypes?: string[]) => Promise<{ testId: string; title: string }>;
    getTest: (testId: string) => Promise<Test>;
    hydrateTest: (testId: string) => Promise<Test>;
    subscribeToGeneration: (testId: string, userId: string) => () => void;
    submitFull: (
        testId: string,
        answers: Array<{ question_id: string; answer_text: string; is_voice?: boolean }>,
        voiceFiles?: Record<string, File>,
    ) => Promise<string>;
    getTestResults: (attemptId: string) => Promise<TestResults>;
    listenForGrading: (attemptId: string, courseId: string, onComplete: (results: TestResults) => void) => () => void;
    clearTest: () => void;
    clearError: () => void;
}

function mergeStreamedQuestion(existing: TestQuestion[], streamed: StreamedQuestion[]): TestQuestion[] {
    const byIndex = new Map(existing.map(q => [q.order_index, q]));
    for (const sq of streamed) {
        if (!byIndex.has(sq.order_index)) {
            byIndex.set(sq.order_index, {
                id: `streamed-${sq.order_index}`,
                question_text: sq.question_text,
                question_type: sq.question_type,
                answer_options: sq.answer_options,
                points: sq.points,
                order_index: sq.order_index,
            });
        }
    }
    return Array.from(byIndex.values()).sort((a, b) => a.order_index - b.order_index);
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
            const { test_id, title, batches_total, question_count } = response.data;

            set({
                currentTest: {
                    id: test_id,
                    title,
                    question_count,
                    questions: [],
                    generation_status: 'pending',
                    batches_done: 0,
                    batches_total: batches_total ?? null,
                },
                isGenerating: false,
            });

            return { testId: test_id, title };
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
        const raw = response.data;
        const test: Test = {
            id: raw.id,
            title: raw.title,
            question_count: raw.question_count,
            questions: raw.questions ?? [],
            generation_status: raw.generation_status ?? 'ready',
            batches_done: raw.batches_done ?? 0,
            batches_total: raw.batches_total ?? null,
        };
        set({ currentTest: test });
        return test;
    },

    hydrateTest: async (testId) => {
        const [testRes, statusRes] = await Promise.all([
            api.ai.getTest(testId),
            api.ai.getTestStatus(testId),
        ]);
        const raw = testRes.data;
        const statusData = statusRes.data;

        const test: Test = {
            id: raw.id,
            title: raw.title,
            question_count: raw.question_count,
            questions: raw.questions ?? [],
            generation_status: statusData.status as TestGenerationStatus,
            batches_done: statusData.batches_done ?? 0,
            batches_total: statusData.batches_total ?? null,
            failure_reason: statusData.failure_reason,
        };
        set({ currentTest: test });
        return test;
    },

    subscribeToGeneration: (testId, userId) => {
        const ws = new WebSocketClient(`user/${userId}`, {
            onMessage: (message) => {
                if (message.type === 'test_generation_status' && message.data.test_id === testId) {
                    set((state) => ({
                        currentTest: state.currentTest
                            ? {
                                ...state.currentTest,
                                generation_status: message.data.status as TestGenerationStatus,
                                batches_done: message.data.batches_done,
                                batches_total: message.data.batches_total,
                            }
                            : state.currentTest,
                    }));
                }

                if (message.type === 'test_batch_ready' && message.data.test_id === testId) {
                    set((state) => {
                        if (!state.currentTest) return state;
                        return {
                            currentTest: {
                                ...state.currentTest,
                                generation_status: 'generating',
                                batches_done: message.data.batch_index + 1,
                                batches_total: message.data.batches_total,
                                questions: mergeStreamedQuestion(state.currentTest.questions, message.data.questions),
                            },
                        };
                    });
                }

                if (message.type === 'test_generation_complete' && message.data.test_id === testId) {
                    set((state) => ({
                        currentTest: state.currentTest
                            ? { ...state.currentTest, generation_status: 'ready' }
                            : state.currentTest,
                    }));
                    ws.disconnect();
                }

                if (message.type === 'test_generation_failed' && message.data.test_id === testId) {
                    set((state) => ({
                        currentTest: state.currentTest
                            ? {
                                ...state.currentTest,
                                generation_status: 'failed',
                                failure_reason: message.data.reason,
                            }
                            : state.currentTest,
                    }));
                    ws.disconnect();
                }

                if (message.type === 'test_generation_regenerating' && message.data.test_id === testId) {
                    set((state) => ({
                        currentTest: state.currentTest
                            ? { ...state.currentTest, questions: [], batches_done: 0, generation_status: 'generating' }
                            : state.currentTest,
                    }));
                }
            },
        });
        ws.connect();

        return () => ws.disconnect();
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
        let resolved = false;

        async function tryResolve() {
            if (resolved) return;
            try {
                const response = await api.ai.getTestResults(attemptId);
                const results: TestResults = response.data;
                if (results.completed_at) {
                    resolved = true;
                    set({ results });
                    clearInterval(pollInterval);
                    clearTimeout(timeout);
                    ws.disconnect();
                    onComplete(results);
                }
            } catch {
                // keep trying
            }
        }

        const ws = new WebSocketClient(courseId, {
            onMessage: (message) => {
                if (message.type === 'grading:complete' && message.data?.attempt_id === attemptId) {
                    tryResolve();
                }
            },
        });
        ws.connect();

        const pollInterval = setInterval(tryResolve, 3000);
        const timeout = setTimeout(() => {
            resolved = true;
            clearInterval(pollInterval);
            ws.disconnect();
        }, 5 * 60 * 1000);

        return () => {
            resolved = true;
            clearInterval(pollInterval);
            clearTimeout(timeout);
            ws.disconnect();
        };
    },

    clearTest: () => set({ currentTest: null, lastAttemptId: null, results: null }),
    clearError: () => set({ error: null }),
}));
