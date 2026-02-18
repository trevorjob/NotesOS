/**
 * NotesOS API Client
 * Axios instance with JWT interceptor and refresh token support
 */

import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';

// ═══════════════════════════════════════════════════════════════════════
// API Client Configuration
// ═══════════════════════════════════════════════════════════════════════

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
    timeout: 120000,
});

// ═══════════════════════════════════════════════════════════════════════
// Token Management
// ═══════════════════════════════════════════════════════════════════════

const TOKEN_KEY = 'notesos_access_token';
const REFRESH_TOKEN_KEY = 'notesos_refresh_token';

export const tokenManager = {
    getToken: (): string | null => {
        if (typeof window === 'undefined') return null;
        return localStorage.getItem(TOKEN_KEY);
    },

    getRefreshToken: (): string | null => {
        if (typeof window === 'undefined') return null;
        return localStorage.getItem(REFRESH_TOKEN_KEY);
    },

    setTokens: (accessToken: string, refreshToken: string) => {
        if (typeof window === 'undefined') return;
        localStorage.setItem(TOKEN_KEY, accessToken);
        localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
    },

    clearTokens: () => {
        if (typeof window === 'undefined') return;
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(REFRESH_TOKEN_KEY);
    },
};

// ═══════════════════════════════════════════════════════════════════════
// Request Interceptor — Attach JWT token
// ═══════════════════════════════════════════════════════════════════════

apiClient.interceptors.request.use(
    (config: InternalAxiosRequestConfig) => {
        const token = tokenManager.getToken();
        if (token && config.headers) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// ═══════════════════════════════════════════════════════════════════════
// Response Interceptor — Handle 401 and refresh token
// ═══════════════════════════════════════════════════════════════════════

let isRefreshing = false;
let failedQueue: Array<{
    resolve: (value?: unknown) => void;
    reject: (reason?: unknown) => void;
}> = [];

const processQueue = (error: Error | null, token: string | null = null) => {
    failedQueue.forEach((prom) => {
        if (error) {
            prom.reject(error);
        } else {
            prom.resolve(token);
        }
    });
    failedQueue = [];
};

apiClient.interceptors.response.use(
    (response) => response,
    async (error: AxiosError) => {
        const originalRequest = error.config as InternalAxiosRequestConfig & {
            _retry?: boolean;
        };

        // If 401 and not already retrying
        if (error.response?.status === 401 && !originalRequest._retry) {
            if (isRefreshing) {
                // Queue this request
                return new Promise((resolve, reject) => {
                    failedQueue.push({ resolve, reject });
                })
                    .then((token) => {
                        if (originalRequest.headers) {
                            originalRequest.headers.Authorization = `Bearer ${token}`;
                        }
                        return apiClient(originalRequest);
                    })
                    .catch((err) => Promise.reject(err));
            }

            originalRequest._retry = true;
            isRefreshing = true;

            const refreshToken = tokenManager.getRefreshToken();

            if (!refreshToken) {
                // No refresh token, logout
                tokenManager.clearTokens();
                if (typeof window !== 'undefined') {
                    window.location.href = '/login';
                }
                return Promise.reject(error);
            }

            try {
                // Call refresh endpoint
                const response = await axios.post(`${API_BASE_URL}/api/auth/refresh`, {
                    refresh_token: refreshToken,
                });

                const { access_token, refresh_token: newRefreshToken } = response.data;

                // Update tokens
                tokenManager.setTokens(access_token, newRefreshToken);

                // Update original request
                if (originalRequest.headers) {
                    originalRequest.headers.Authorization = `Bearer ${access_token}`;
                }

                // Process queued requests
                processQueue(null, access_token);

                // Retry original request
                return apiClient(originalRequest);
            } catch (refreshError) {
                // Refresh failed, logout
                processQueue(refreshError as Error, null);
                tokenManager.clearTokens();
                if (typeof window !== 'undefined') {
                    window.location.href = '/login';
                }
                return Promise.reject(refreshError);
            } finally {
                isRefreshing = false;
            }
        }

        return Promise.reject(error);
    }
);

// ═══════════════════════════════════════════════════════════════════════
// API Endpoints (matching backend structure)
// ═══════════════════════════════════════════════════════════════════════

export const api = {
    // Auth
    auth: {
        register: (data: {
            email: string;
            password: string;
            full_name: string;
        }) => apiClient.post('/api/auth/register', data),

        login: (email: string, password: string) =>
            apiClient.post('/api/auth/login', { email, password }),

        logout: () => apiClient.post('/api/auth/logout'),

        refresh: (refreshToken: string) =>
            apiClient.post('/api/auth/refresh', { refresh_token: refreshToken }),

        getMe: () => apiClient.get('/api/auth/me'),

        updatePersonality: (prefs: {
            tone?: string;
            emoji_usage?: string;
            explanation_style?: string;
        }) => apiClient.patch('/api/auth/me/personality', prefs),
    },

    // Courses
    courses: {
        getAll: () => apiClient.get('/api/courses'),

        getById: (id: string) => apiClient.get(`/api/courses/${id}`),

        create: (data: {
            code: string;
            name: string;
            description?: string;
            semester?: string;
            is_public?: boolean;
        }) => apiClient.post('/api/courses', data),

        // Backend expects: { invite_code?, search?, course_id? }
        join: (data: {
            invite_code?: string;
            search?: string;
            course_id?: string;
        }) => apiClient.post('/api/courses/join', data),
    },

    // Topics
    topics: {
        getByCourse: (courseId: string) =>
            apiClient.get(`/api/courses/${courseId}/topics`),

        create: (courseId: string, data: {
            title: string;
            description?: string;
            week_number?: number;
            order_index: number;
        }) => apiClient.post(`/api/courses/${courseId}/topics`, {
            ...data,
            course_id: courseId,
        }),

        getById: (id: string) => apiClient.get(`/api/topics/${id}`),

        update: (id: string, data: Partial<{
            title: string;
            description: string;
            week_number: number;
        }>) => apiClient.put(`/api/topics/${id}`, data),

        delete: (id: string) => apiClient.delete(`/api/topics/${id}`),
    },

    // Resources
    resources: {
        getByTopic: (topicId: string, page: number = 1, pageSize: number = 20) =>
            apiClient.get(`/api/topics/${topicId}/resources`, {
                params: { page, page_size: pageSize },
            }),

        createText: (topicId: string, data: { title?: string; content: string }) =>
            apiClient.post(`/api/topics/${topicId}/resources/text`, {
                topic_id: topicId,
                ...data,
            }),

        upload: (topicId: string, courseId: string, files: File[], title?: string, isHandwritten?: boolean) => {
            const formData = new FormData();
            formData.append('topic_id', topicId);
            formData.append('course_id', courseId);
            if (title) formData.append('title', title);
            if (isHandwritten !== undefined) formData.append('is_handwritten', String(isHandwritten));
            files.forEach(file => formData.append('files', file));
            return apiClient.post('/api/resources/upload', formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });
        },

        getById: (id: string) => apiClient.get(`/api/resources/${id}`),

        update: (id: string, data: Partial<{
            title: string;
            description: string;
        }>) => apiClient.put(`/api/resources/${id}`, data),

        delete: (id: string) => apiClient.delete(`/api/resources/${id}`),

        reprocessOCR: (id: string) => apiClient.post(`/api/resources/${id}/reprocess-ocr`),
    },

    // AI Features
    ai: {
        // Fact Check
        verifyResource: (resourceId: string) =>
            apiClient.post(`/api/resources/${resourceId}/fact-check`),

        getFactChecks: (resourceId: string) =>
            apiClient.get(`/api/resources/${resourceId}/fact-checks`),

        // Pre-class Research
        generateResearch: (topicId: string) =>
            apiClient.post(`/api/topics/${topicId}/research`),

        getResearch: (topicId: string) =>
            apiClient.get(`/api/topics/${topicId}/research`),

        // Study Agent (course_id as query param)
        askQuestion: (courseId: string, data: {
            question: string;
            topic_id?: string;
            conversation_id?: string;
        }) => apiClient.post('/api/study/ask', data, {
            params: { course_id: courseId },
        }),

        getConversations: (courseId: string) =>
            apiClient.get('/api/study/conversations', {
                params: { course_id: courseId },
            }),

        getConversation: (conversationId: string) =>
            apiClient.get(`/api/study/conversations/${conversationId}`),

        // Tests
        generateTest: (courseId: string, data: {
            topic_ids: string[];
            question_count: number;
            test_type: 'practice' | 'quiz' | 'exam';
        }) => apiClient.post('/api/tests/generate', data, {
            params: { course_id: courseId },
        }),

        getTest: (testId: string) =>
            apiClient.get(`/api/tests/${testId}`),

        submitAnswers: (testId: string, answers: Array<{
            question_id: string;
            answer_text: string;
        }>) => apiClient.post(`/api/tests/${testId}/submit`, answers),

        submitVoiceAnswer: (testId: string, questionId: string, audioFile: File, attemptId?: string) => {
            const formData = new FormData();
            formData.append('audio_file', audioFile);
            formData.append('question_id', questionId);
            if (attemptId) formData.append('attempt_id', attemptId);
            return apiClient.post(`/api/tests/${testId}/voice-answer`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });
        },

        getTestResults: (attemptId: string) =>
            apiClient.get(`/api/tests/attempts/${attemptId}/results`),
    },

    // Progress
    progress: {
        startSession: (data: {
            topic_id: string;
            session_type: 'reading' | 'quiz' | 'practice';
        }) => apiClient.post('/api/progress/sessions/start', data),

        endSession: (sessionId: string) =>
            apiClient.post(`/api/progress/sessions/${sessionId}/end`),

        getCourseProgress: (courseId: string) =>
            apiClient.get(`/api/progress/${courseId}`),

        getTopicsProgress: (courseId: string) =>
            apiClient.get(`/api/progress/${courseId}/topics`),

        getStreak: (courseId: string) =>
            apiClient.get(`/api/progress/${courseId}/streak`),

        getRecommendations: (courseId: string) =>
            apiClient.get(`/api/progress/${courseId}/recommendations`),
    },
};

export default api;
