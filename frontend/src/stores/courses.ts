/**
 * NotesOS - Courses Store
 * Zustand store for course management (matching backend structure)
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { api } from '@/lib/api';

interface Topic {
    id: string;
    title: string;
    description?: string;
    week_number?: number;
    order_index: number;
    mastery_level?: number;
}

interface Course {
    id: string;
    code: string;
    name: string;
    semester?: string;
    description?: string;
    member_count?: number;
    created_by: string;
    joined_at?: string;
    topics?: Topic[];
}

interface CourseState {
    courses: Course[];
    currentCourse: Course | null;
    isLoading: boolean;
    error: string | null;

    // Actions
    fetchCourses: () => Promise<void>;
    createCourse: (data: {
        code: string;
        name: string;
        description?: string;
        semester?: string;
        is_public?: boolean;
    }) => Promise<Course>;
    joinCourse: (identifier: string) => Promise<void>;
    selectCourse: (courseId: string) => Promise<void>;
    createTopic: (courseId: string, data: {
        title: string;
        description?: string;
        week_number?: number;
    }) => Promise<Topic>;
    clearCurrentCourse: () => void;
    clearError: () => void;
}

export const useCourseStore = create<CourseState>()(
    persist(
        (set, get) => ({
            courses: [],
            currentCourse: null,
            isLoading: false,
            error: null,

            fetchCourses: async () => {
                set({ isLoading: true, error: null });
                try {
                    const response = await api.courses.getAll();
                    set({ courses: response.data.courses || [], isLoading: false });
                } catch (error: any) {
                    const errorMessage =
                        error.response?.data?.detail || 'Failed to fetch courses';
                    set({ isLoading: false, error: errorMessage });
                }
            },

            createCourse: async (data) => {
                set({ error: null });
                try {
                    const response = await api.courses.create(data);
                    const newCourse = response.data.course;

                    // Refresh courses list
                    await get().fetchCourses();

                    return newCourse;
                } catch (error: any) {
                    const errorMessage =
                        error.response?.data?.detail || 'Failed to create course';
                    set({ error: errorMessage });
                    throw new Error(errorMessage);
                }
            },

            joinCourse: async (identifier: string) => {
                set({ error: null });
                try {
                    // Try as invite code first, then as search term
                    await api.courses.join({ invite_code: identifier });

                    // Refresh courses list
                    await get().fetchCourses();
                } catch (error: any) {
                    // If invite code fails, try as search term
                    try {
                        await api.courses.join({ search: identifier });
                        await get().fetchCourses();
                    } catch (searchError: any) {
                        const errorMessage =
                            searchError.response?.data?.detail || 'Failed to join course';
                        set({ error: errorMessage });
                        throw new Error(errorMessage);
                    }
                }
            },

            selectCourse: async (courseId: string) => {
                set({ isLoading: true, error: null });
                try {
                    const [courseResponse, topicsResponse] = await Promise.all([
                        api.courses.getById(courseId),
                        api.topics.getByCourse(courseId),
                    ]);

                    set({
                        currentCourse: {
                            ...courseResponse.data.course,
                            topics: topicsResponse.data.topics || [],
                        },
                        isLoading: false,
                    });
                } catch (error: any) {
                    const errorMessage =
                        error.response?.data?.detail || 'Failed to load course';
                    set({ isLoading: false, error: errorMessage });
                }
            },

            createTopic: async (courseId, data) => {
                set({ error: null });
                try {
                    const response = await api.topics.create(courseId, data);
                    const newTopic = response.data.topic;

                    // Refresh current course
                    await get().selectCourse(courseId);

                    return newTopic;
                } catch (error: any) {
                    const errorMessage =
                        error.response?.data?.detail || 'Failed to create topic';
                    set({ error: errorMessage });
                    throw new Error(errorMessage);
                }
            },

            clearCurrentCourse: () => set({ currentCourse: null }),
            clearError: () => set({ error: null }),
        }),
        {
            name: 'notesos-courses',
            partialize: (state) => ({
                currentCourse: state.currentCourse,
            }),
        }
    )
);
