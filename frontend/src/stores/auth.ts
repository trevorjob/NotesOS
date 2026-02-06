/**
 * NotesOS - Auth Store
 * Zustand store for authentication state management
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface User {
  id: string
  email: string
  full_name: string
  avatar_url?: string
  study_personality?: {
    tone: 'encouraging' | 'direct' | 'humorous'
    emoji_usage: 'none' | 'moderate' | 'heavy'
    explanation_style: 'concise' | 'detailed' | 'visual'
  }
}

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  
  // Actions
  login: (email: string, password: string) => Promise<void>
  register: (data: { email: string; password: string; full_name: string }) => Promise<void>
  logout: () => void
  setUser: (user: User) => void
  setToken: (token: string) => void
  updatePersonality: (prefs: Partial<User['study_personality']>) => Promise<void>
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,

      login: async (email: string, password: string) => {
        set({ isLoading: true })
        try {
          const res = await fetch(`${API_URL}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
          })
          
          if (!res.ok) {
            const error = await res.json()
            throw new Error(error.detail || 'Login failed')
          }
          
          const data = await res.json()
          set({
            user: data.user,
            token: data.token,
            isAuthenticated: true,
            isLoading: false,
          })
        } catch (error) {
          set({ isLoading: false })
          throw error
        }
      },

      register: async (data) => {
        set({ isLoading: true })
        try {
          const res = await fetch(`${API_URL}/api/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
          })
          
          if (!res.ok) {
            const error = await res.json()
            throw new Error(error.detail || 'Registration failed')
          }
          
          const responseData = await res.json()
          set({
            user: responseData.user,
            token: responseData.token,
            isAuthenticated: true,
            isLoading: false,
          })
        } catch (error) {
          set({ isLoading: false })
          throw error
        }
      },

      logout: () => {
        set({
          user: null,
          token: null,
          isAuthenticated: false,
        })
      },

      setUser: (user: User) => set({ user }),
      setToken: (token: string) => set({ token, isAuthenticated: true }),

      updatePersonality: async (prefs) => {
        const { token, user } = get()
        if (!token || !user) return

        const res = await fetch(`${API_URL}/api/auth/me/personality`, {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`,
          },
          body: JSON.stringify(prefs),
        })

        if (res.ok) {
          const data = await res.json()
          set({
            user: { ...user, study_personality: data.study_personality },
          })
        }
      },
    }),
    {
      name: 'notesos-auth',
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)
