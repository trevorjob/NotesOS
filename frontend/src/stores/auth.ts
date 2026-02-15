/**
 * NotesOS - Auth Store
 * Zustand store for authentication with refresh token support
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { api, tokenManager } from '@/lib/api';

interface User {
  id: string;
  email: string;
  full_name: string;
  avatar_url?: string;
  study_personality?: {
    tone: 'encouraging' | 'direct' | 'humorous';
    emoji_usage: 'none' | 'moderate' | 'heavy';
    explanation_style: 'concise' | 'detailed' | 'visual';
  };
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (email: string, password: string) => Promise<void>;
  register: (data: {
    email: string;
    password: string;
    full_name: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
  setUser: (user: User) => void;
  clearError: () => void;
  updatePersonality: (prefs: Partial<User['study_personality']>) => Promise<void>;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      login: async (email: string, password: string) => {
        set({ isLoading: true, error: null });
        try {
          const response = await api.auth.login(email, password);
          const { user, access_token, refresh_token } = response.data;

          // Store tokens
          tokenManager.setTokens(access_token, refresh_token);

          set({
            user,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch (error: any) {
          const errorMessage =
            error.response?.data?.detail || 'Login failed. Please try again.';
          set({ isLoading: false, error: errorMessage });
          throw new Error(errorMessage);
        }
      },

      register: async (data) => {
        set({ isLoading: true, error: null });
        try {
          const response = await api.auth.register(data);
          const { user, access_token, refresh_token } = response.data;

          // Store tokens
          tokenManager.setTokens(access_token, refresh_token);

          set({
            user,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch (error: any) {
          const errorMessage =
            error.response?.data?.detail ||
            'Registration failed. Please try again.';
          set({ isLoading: false, error: errorMessage });
          throw new Error(errorMessage);
        }
      },

      logout: async () => {
        try {
          await api.auth.logout();
        } catch (error) {
          // Ignore logout errors
          console.error('Logout error:', error);
        } finally {
          // Clear tokens and state
          tokenManager.clearTokens();
          set({
            user: null,
            isAuthenticated: false,
            error: null,
          });
        }
      },

      setUser: (user: User) => set({ user }),

      clearError: () => set({ error: null }),

      updatePersonality: async (prefs) => {
        const { user } = get();
        if (!user) return;

        try {
          await api.auth.updatePersonality(prefs);
          set({
            user: {
              ...user,
              study_personality: { ...user.study_personality, ...prefs },
            },
          });
        } catch (error) {
          console.error('Failed to update personality:', error);
        }
      },
    }),
    {
      name: 'notesos-auth',
      partialize: (state) => ({
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
