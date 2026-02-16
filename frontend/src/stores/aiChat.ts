/**
 * NotesOS - AI Chat Store
 * Zustand store for study agent conversations
 */

import { create } from 'zustand';
import { api } from '@/lib/api';

interface Message {
    role: 'user' | 'assistant';
    content: string;
    sources?: Array<{
        title: string;
        url?: string;
        resource_id?: string;
    }>;
    created_at: string;
}

interface Conversation {
    id: string;
    title: string | null;
    created_at: string;
}

interface AIChatState {
    conversations: Conversation[];
    currentConversationId: string | null;
    messages: Message[];
    isLoading: boolean;
    isSending: boolean;
    error: string | null;

    // Actions
    fetchConversations: (courseId: string) => Promise<void>;
    loadConversation: (conversationId: string) => Promise<void>;
    askQuestion: (courseId: string, question: string, topicId?: string) => Promise<void>;
    clearCurrentConversation: () => void;
    clearError: () => void;
}

export const useAIChatStore = create<AIChatState>()((set, get) => ({
    conversations: [],
    currentConversationId: null,
    messages: [],
    isLoading: false,
    isSending: false,
    error: null,

    fetchConversations: async (courseId: string) => {
        set({ isLoading: true, error: null });
        try {
            const response = await api.ai.getConversations(courseId);
            const conversations = response.data || [];
            set({
                conversations,
                isLoading: false,
            });

            // Auto-load most recent conversation if exists and no current conversation
            const { currentConversationId } = get();
            if (conversations.length > 0 && !currentConversationId) {
                await get().loadConversation(conversations[0].id);
            }
        } catch (error: any) {
            const errorMessage =
                error.response?.data?.detail || 'Failed to fetch conversations';
            set({ isLoading: false, error: errorMessage });
        }
    },

    loadConversation: async (conversationId: string) => {
        set({ isLoading: true, error: null, currentConversationId: conversationId });
        try {
            const response = await api.ai.getConversation(conversationId);
            set({
                messages: response.data || [],
                isLoading: false,
            });
        } catch (error: any) {
            const errorMessage =
                error.response?.data?.detail || 'Failed to load conversation';
            set({ isLoading: false, error: errorMessage });
        }
    },

    askQuestion: async (courseId: string, question: string, topicId?: string) => {
        set({ isSending: true, error: null });

        // Optimistically add user message
        const userMessage: Message = {
            role: 'user',
            content: question,
            created_at: new Date().toISOString(),
        };
        set(state => ({ messages: [...state.messages, userMessage] }));

        try {
            const { currentConversationId } = get();
            const response = await api.ai.askQuestion(courseId, {
                question,
                topic_id: topicId,
                conversation_id: currentConversationId || undefined,
            });

            const { answer, sources, conversation_id } = response.data;

            // Add AI message
            const aiMessage: Message = {
                role: 'assistant',
                content: answer,
                sources: sources || [],
                created_at: new Date().toISOString(),
            };

            set(state => ({
                messages: [...state.messages, aiMessage],
                currentConversationId: conversation_id,
                isSending: false,
            }));

            // Refresh conversations list
            await get().fetchConversations(courseId);
        } catch (error: any) {
            // Remove optimistic user message on error
            set(state => ({
                messages: state.messages.slice(0, -1),
                isSending: false,
                error: error.response?.data?.detail || 'Failed to send message',
            }));
        }
    },

    clearCurrentConversation: () => set({
        currentConversationId: null,
        messages: [],
    }),

    clearError: () => set({ error: null }),
}));
