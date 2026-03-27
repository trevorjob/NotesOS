/**
 * NotesOS - Courses Store
 * Zustand store for course management (matching backend structure)
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { AxiosError } from 'axios';
import { api } from '@/lib/api';
import { offlineDb } from '@/lib/offlineDb';

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
    semester_id?: string | null;
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
    _isFetchingCourses: boolean;
    _isSelectingCourse: boolean;

    // Actions
    fetchCourses: (force?: boolean) => Promise<void>;
    createCourse: (data: {
        code: string;
        name: string;
        description?: string;
        semester_id?: string;
        is_public?: boolean;
    }) => Promise<Course>;
    joinCourse: (identifier: string) => Promise<void>;
    selectCourse: (courseId: string) => Promise<void>;
    createTopic: (courseId: string, data: {
        title: string;
        description?: string;
        week_number?: number;
        order_index: number;
    }) => Promise<Topic>;
    updateTopic: (courseId: string, topicId: string, data: {
        title?: string;
        description?: string;
        week_number?: number;
        order_index?: number;
    }) => Promise<Topic>;
    deleteTopic: (courseId: string, topicId: string) => Promise<void>;
    clearCurrentCourse: () => void;
    setError: (error: string | null) => void;
    clearError: () => void;
}

export const useCourseStore = create<CourseState>()(
    persist(
        (set, get) => ({
            courses: [],
            currentCourse: null,
            isLoading: false,
            error: null,
            _isFetchingCourses: false,
            _isSelectingCourse: false,

            fetchCourses: async (force = false) => {
                // Skip if already in-flight (dedup parallel calls e.g. GlassNav + page mounting together)
                if (get()._isFetchingCourses) return;
                // Skip if we already have data and caller hasn't forced a refresh
                if (!force && get().courses.length > 0) return;

                set({ _isFetchingCourses: true, isLoading: true, error: null });

                // Offline: serve from IndexedDB
                if (typeof navigator !== 'undefined' && !navigator.onLine) {
                    const cached = await offlineDb.getCourses();
                    set({ courses: cached as Course[], isLoading: false, _isFetchingCourses: false });
                    return;
                }

                try {
                    const response = await api.courses.getAll();
                    const courses = response.data.courses || [];
                    set({ courses, isLoading: false, _isFetchingCourses: false });
                    offlineDb.putCourses(courses).catch(() => { });
                } catch (error) {
                    const cached = await offlineDb.getCourses();
                    if (cached.length > 0) {
                        set({ courses: cached as Course[], isLoading: false, _isFetchingCourses: false });
                    } else {
                        const errorMessage =
                            (error as AxiosError<{ detail: string }>).response?.data?.detail || 'Failed to fetch courses';
                        set({ isLoading: false, error: errorMessage, _isFetchingCourses: false });
                    }
                }
            },

            createCourse: async (data) => {
                set({ error: null });
                try {
                    const response = await api.courses.create(data);
                    const newCourse = response.data.course;

                    await get().fetchCourses(true);

                    return newCourse;
                } catch (error) {
                    const errorMessage =
                        (error as AxiosError<{ detail: string }>).response?.data?.detail || 'Failed to create course';
                    set({ error: errorMessage });
                    throw new Error(errorMessage);
                }
            },

            joinCourse: async (identifier: string) => {
                set({ error: null });
                try {
                    await api.courses.join({ invite_code: identifier });
                    await get().fetchCourses(true);
                } catch (error) {
                    try {
                        await api.courses.join({ search: identifier });
                        await get().fetchCourses(true);
                    } catch (searchError) {
                        const errorMessage =
                            (searchError as AxiosError<{ detail: string }>).response?.data?.detail || 'Failed to join course';
                        set({ error: errorMessage });
                        throw new Error(errorMessage);
                    }
                }
            },

            selectCourse: async (courseId: string) => {
                // Already loaded this course with topics — skip the network round-trip
                const { currentCourse, _isSelectingCourse } = get();
                if (
                    currentCourse?.id === courseId &&
                    Array.isArray(currentCourse?.topics)
                ) return;

                // Dedup parallel calls (e.g. page useEffect + sub-component)
                if (_isSelectingCourse) return;

                set({ _isSelectingCourse: true, isLoading: true, error: null });

                // Offline: serve from IndexedDB
                if (typeof navigator !== 'undefined' && !navigator.onLine) {
                    const courses = await offlineDb.getCourses();
                    const course = courses.find(c => c.id === courseId);
                    const topics = await offlineDb.getTopicsByCourse(courseId);
                    if (course) {
                        set({ currentCourse: { ...course, topics } as Course, isLoading: false, _isSelectingCourse: false });
                    } else {
                        set({ isLoading: false, error: 'Course not available offline', _isSelectingCourse: false });
                    }
                    return;
                }

                try {
                    const [courseResponse, topicsResponse] = await Promise.all([
                        api.courses.getById(courseId),
                        api.topics.getByCourse(courseId),
                    ]);

                    const topics = topicsResponse.data || [];
                    const course = { ...courseResponse.data.course, topics };

                    set((state) => ({
                        currentCourse: course,
                        courses: state.courses.map((c) => c.id === courseId ? { ...c, topics } : c),
                        isLoading: false,
                        _isSelectingCourse: false,
                    }));

                    offlineDb.putCourses([courseResponse.data.course]).catch(() => { });
                    offlineDb.putTopics(courseId, topics).catch(() => { });
                } catch (error) {
                    const errorMessage =
                        (error as AxiosError<{ detail: string }>).response?.data?.detail || 'Failed to load course';
                    set({ isLoading: false, error: errorMessage, _isSelectingCourse: false });
                }
            },

            createTopic: async (courseId, data) => {
                set({ error: null });
                try {
                    const response = await api.topics.create(courseId, data);
                    const newTopic = response.data;

                    // Bust the selectCourse guard so the refreshed course is fetched
                    set({ currentCourse: null });
                    await get().selectCourse(courseId);

                    return newTopic;
                } catch (error) {
                    const errorMessage =
                        (error as AxiosError<{ detail: string }>).response?.data?.detail || 'Failed to create topic';
                    set({ error: errorMessage });
                    throw new Error(errorMessage);
                }
            },

            updateTopic: async (courseId, topicId, data) => {
                set({ error: null });
                try {
                    const response = await api.topics.update(topicId, data);
                    const updatedTopic = response.data as Topic;

                    set({ currentCourse: null });
                    await get().selectCourse(courseId);

                    return updatedTopic;
                } catch (error) {
                    const errorMessage =
                        (error as AxiosError<{ detail: string }>).response?.data?.detail || 'Failed to update topic';
                    set({ error: errorMessage });
                    throw new Error(errorMessage);
                }
            },

            deleteTopic: async (courseId, topicId) => {
                set({ error: null });
                try {
                    await api.topics.delete(topicId);

                    set({ currentCourse: null });
                    await get().selectCourse(courseId);
                } catch (error) {
                    const errorMessage =
                        (error as AxiosError<{ detail: string }>).response?.data?.detail || 'Failed to delete topic';
                    set({ error: errorMessage });
                    throw new Error(errorMessage);
                }
            },

            clearCurrentCourse: () => set({ currentCourse: null }),
            setError: (error: string | null) => set({ error }),
            clearError: () => set({ error: null }),
        }),
        {
            name: 'notesos-courses',
            partialize: (state) => ({
                currentCourse: state.currentCourse,
                courses: state.courses,
            }),
        }
    )
);
