/**
 * NotesOS - Courses Store
 * Zustand store for course state management
 */

import { create } from 'zustand'

interface Topic {
    id: string
    title: string
    description?: string
    week_number?: number
    order_index: number
}

interface Course {
    id: string
    code: string
    name: string
    semester?: string
    description?: string
    member_count?: number
    created_by: string
    joined_at?: string
    topics?: Topic[]
}

interface CourseState {
    courses: Course[]
    currentCourse: Course | null
    isLoading: boolean

    // Actions
    fetchCourses: () => Promise<void>
    createCourse: (data: { code: string; name: string; semester?: string; description?: string; is_public?: boolean }) => Promise<Course>
    joinCourse: (identifier: { search?: string; course_id?: string; invite_code?: string }) => Promise<void>
    selectCourse: (courseId: string) => Promise<void>
    createTopic: (courseId: string, data: { title: string; description?: string; week_number?: number }) => Promise<Topic>
    clearCurrentCourse: () => void
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

const getToken = () => {
    if (typeof window === 'undefined') return null
    const stored = localStorage.getItem('notesos-auth')
    if (stored) {
        const parsed = JSON.parse(stored)
        return parsed.state?.token
    }
    return null
}

export const useCourseStore = create<CourseState>((set, get) => ({
    courses: [],
    currentCourse: null,
    isLoading: false,

    fetchCourses: async () => {
        const token = getToken()
        if (!token) return

        set({ isLoading: true })
        try {
            const res = await fetch(`${API_URL}/api/courses`, {
                headers: { 'Authorization': `Bearer ${token}` },
            })

            if (res.ok) {
                const data = await res.json()
                set({ courses: data.courses, isLoading: false })
            }
        } catch {
            set({ isLoading: false })
        }
    },

    createCourse: async (data) => {
        const token = getToken()
        if (!token) throw new Error('Not authenticated')

        const res = await fetch(`${API_URL}/api/courses`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`,
            },
            body: JSON.stringify(data),
        })

        if (!res.ok) {
            const error = await res.json()
            throw new Error(error.detail || 'Failed to create course')
        }

        const responseData = await res.json()
        const newCourse = responseData.course

        // Refresh courses list
        await get().fetchCourses()

        return newCourse
    },

    joinCourse: async (identifier) => {
        const token = getToken()
        if (!token) throw new Error('Not authenticated')

        const res = await fetch(`${API_URL}/api/courses/join`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`,
            },
            body: JSON.stringify(identifier),
        })

        if (!res.ok) {
            const error = await res.json()
            throw new Error(error.detail || 'Failed to join course')
        }

        // Refresh courses list
        await get().fetchCourses()
    },

    selectCourse: async (courseId: string) => {
        const token = getToken()
        if (!token) return

        set({ isLoading: true })
        try {
            const res = await fetch(`${API_URL}/api/courses/${courseId}`, {
                headers: { 'Authorization': `Bearer ${token}` },
            })

            if (res.ok) {
                const data = await res.json()
                set({
                    currentCourse: { ...data.course, topics: data.topics },
                    isLoading: false,
                })
            }
        } catch {
            set({ isLoading: false })
        }
    },

    createTopic: async (courseId, data) => {
        const token = getToken()
        if (!token) throw new Error('Not authenticated')

        const res = await fetch(`${API_URL}/api/courses/${courseId}/topics`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`,
            },
            body: JSON.stringify(data),
        })

        if (!res.ok) {
            const error = await res.json()
            throw new Error(error.detail || 'Failed to create topic')
        }

        const responseData = await res.json()

        // Refresh current course
        await get().selectCourse(courseId)

        return responseData.topic
    },

    clearCurrentCourse: () => set({ currentCourse: null }),
}))
