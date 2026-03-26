import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { api } from '@/lib/api';

export interface Semester {
    id: string;
    name: string;
    invite_code?: string;
    start_date?: string | null;
    end_date?: string | null;
    role?: string;
    member_count?: number;
    course_count?: number;
}

interface SemestersState {
    semesters: Semester[];
    activeSemesterId: string | null;
    isLoading: boolean;
    fetchSemesters: () => Promise<void>;
    createSemester: (data: { name: string; start_date?: string; end_date?: string }) => Promise<Semester>;
    deleteSemester: (id: string) => Promise<void>;
    addCourseToSemester: (semesterId: string, courseId: string) => Promise<void>;
    removeCourseFromSemester: (semesterId: string, courseId: string) => Promise<void>;
    joinSemester: (invite_code: string) => Promise<Record<string, unknown>>;
    setActiveSemester: (id: string | null) => void;
}

export const useSemesterStore = create<SemestersState>()(
    persist(
        (set, get) => ({
            semesters: [],
            activeSemesterId: null,
            isLoading: false,

            fetchSemesters: async () => {
                set({ isLoading: true });
                try {
                    const res = await api.semesters.getAll();
                    const data: Semester[] = res.data?.semesters ?? res.data ?? [];
                    set({ semesters: data });

                    // If the saved activeSemesterId no longer exists in the list, clear it
                    const { activeSemesterId } = get();
                    if (activeSemesterId && !data.find((s) => s.id === activeSemesterId)) {
                        set({ activeSemesterId: null });
                    }
                    // If no active semester but semesters exist, auto-pick the first one
                    if (!activeSemesterId && data.length > 0) {
                        set({ activeSemesterId: data[0].id });
                    }
                } catch {
                    // ignore
                } finally {
                    set({ isLoading: false });
                }
            },

            createSemester: async (data) => {
                const res = await api.semesters.create(data);
                const semester: Semester = res.data?.semester ?? res.data;
                set((s) => ({ semesters: [...s.semesters, semester], activeSemesterId: semester.id }));
                return semester;
            },

            deleteSemester: async (id) => {
                await api.semesters.delete(id);
                set((s) => ({
                    semesters: s.semesters.filter((sem) => sem.id !== id),
                    activeSemesterId: s.activeSemesterId === id ? null : s.activeSemesterId,
                }));
            },

            addCourseToSemester: async (semesterId, courseId) => {
                await api.semesters.addCourse(semesterId, courseId);
            },

            removeCourseFromSemester: async (semesterId, courseId) => {
                await api.semesters.removeCourse(semesterId, courseId);
            },

            joinSemester: async (invite_code) => {
                const res = await api.semesters.join(invite_code);
                const semesterId: string | undefined = res.data?.semester?.id;
                await get().fetchSemesters();
                // Auto-activate the joined semester
                if (semesterId) set({ activeSemesterId: semesterId });
                // Import lazily to avoid circular dependency
                const { useCourseStore } = await import('@/stores/courses');
                await useCourseStore.getState().fetchCourses(true);
                return res.data ?? {};
            },

            setActiveSemester: (id) => set({ activeSemesterId: id }),
        }),
        {
            name: 'notesos-semesters',
            partialize: (state) => ({ activeSemesterId: state.activeSemesterId }),
        }
    )
);
