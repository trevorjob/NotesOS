/**
 * NotesOS - Notification Store
 * Real-time notifications via WebSocket + REST polling
 */

import { create } from 'zustand';
import { api } from '@/lib/api';
import { WebSocketClient } from '@/lib/websocket';
import { useKnowledgeStore } from '@/stores/knowledge';

export interface AppNotification {
    id: string;
    type: string;
    title: string;
    body: string;
    is_read: boolean;
    created_at: string;
}

export interface Toast {
    id: string;
    title: string;
    body?: string;
    variant: 'info' | 'success' | 'error';
}

interface NotificationState {
    notifications: AppNotification[];
    unreadCount: number;
    toasts: Toast[];
    _wsClient: WebSocketClient | null;

    fetchUnreadCount: () => Promise<void>;
    fetchNotifications: () => Promise<void>;
    addToast: (title: string, variant?: Toast['variant'], body?: string) => void;
    dismissToast: (id: string) => void;
    markRead: (id: string) => Promise<void>;
    markAllRead: () => Promise<void>;
    deleteNotification: (id: string) => Promise<void>;
    clearAllNotifications: () => Promise<void>;
    initWebSocket: (courseId: string) => () => void;
    pushNotification: (n: AppNotification) => void;
}

export const useNotificationStore = create<NotificationState>()((set, get) => ({
    notifications: [],
    unreadCount: 0,
    toasts: [],
    _wsClient: null,

    fetchUnreadCount: async () => {
        try {
            const res = await api.notifications.getUnreadCount();
            set({ unreadCount: res.data?.count ?? 0 });
        } catch { /* ignore */ }
    },

    fetchNotifications: async () => {
        try {
            const res = await api.notifications.getAll(20, 0);
            set({
                notifications: res.data?.notifications ?? [],
                unreadCount: (res.data?.notifications ?? []).filter((n: AppNotification) => !n.is_read).length,
            });
        } catch { /* ignore */ }
    },

    addToast: (title, variant = 'info', body?) => {
        const id = Math.random().toString(36).slice(2);
        set((s) => ({ toasts: [...s.toasts.slice(-2), { id, title, body, variant }] }));
        setTimeout(() => get().dismissToast(id), 5000);
    },

    dismissToast: (id) => {
        set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
    },

    markRead: async (id) => {
        try {
            await api.notifications.markRead(id);
            set((s) => ({
                notifications: s.notifications.map((n) => n.id === id ? { ...n, is_read: true } : n),
                unreadCount: Math.max(0, s.unreadCount - 1),
            }));
        } catch { /* ignore */ }
    },

    markAllRead: async () => {
        try {
            await api.notifications.markAllRead();
            set((s) => ({
                notifications: s.notifications.map((n) => ({ ...n, is_read: true })),
                unreadCount: 0,
            }));
        } catch { /* ignore */ }
    },

    deleteNotification: async (id) => {
        try {
            await api.notifications.deleteOne(id);
            set((s) => {
                const removed = s.notifications.find((n) => n.id === id);
                return {
                    notifications: s.notifications.filter((n) => n.id !== id),
                    unreadCount: removed && !removed.is_read ? Math.max(0, s.unreadCount - 1) : s.unreadCount,
                };
            });
        } catch { /* ignore */ }
    },

    clearAllNotifications: async () => {
        try {
            await api.notifications.deleteAll();
            set({ notifications: [], unreadCount: 0 });
        } catch { /* ignore */ }
    },

    pushNotification: (n) => {
        set((s) => ({
            notifications: [n, ...s.notifications.filter((x) => x.id !== n.id)],
            unreadCount: s.unreadCount + 1,
        }));
    },

    initWebSocket: (courseId: string) => {
        // Disconnect existing connection first
        get()._wsClient?.disconnect();

        const client = new WebSocketClient(courseId, {
            onMessage: (msg) => {
                const { addToast, pushNotification, fetchUnreadCount } = get();

                if (msg.type === 'grading:complete') {
                    fetchUnreadCount();
                    addToast('Test graded', 'success', 'Your answers have been reviewed. Check your results.');
                } else if (msg.type === 'processing_status') {
                    if (msg.status === 'completed') {
                        addToast('Resource ready', 'success', 'Your resource has been processed and is ready to use.');
                    } else if (msg.status === 'failed') {
                        addToast('Processing failed', 'error', 'We couldn\'t process this resource. Try re-uploading it.');
                    }
                } else if (msg.type === 'fact_check:complete') {
                    addToast('AI summary ready', 'info', 'AI analysis is ready for your resource.');
                } else if (msg.type === 'knowledge_updated') {
                    // Re-fetch knowledge for this topic so the store reflects the new synthesis,
                    // then show a toast so the user knows their notes were updated.
                    useKnowledgeStore.getState().forceRefetchKnowledge(msg.topic_id);
                    addToast('Notes updated', 'success', 'Study notes have been regenerated with your new materials.');
                } else if (msg.type === 'knowledge_status' && msg.status === 'processing') {
                    // Worker has started synthesising — keep the UI in a processing state.
                    const existing = useKnowledgeStore.getState().topicKnowledge[msg.topic_id];
                    if (existing) {
                        useKnowledgeStore.setState((s) => ({
                            topicKnowledge: {
                                ...s.topicKnowledge,
                                [msg.topic_id]: { ...existing, status: 'processing' as const },
                            },
                        }));
                    }
                } else if (msg.type === 'notification') {
                    const n = msg.data as AppNotification;
                    if (n?.id) {
                        pushNotification(n);
                        addToast(n.title, 'info', n.body || undefined);
                    }
                }
            },
        });

        client.connect();
        set({ _wsClient: client });

        return () => {
            client.disconnect();
            set({ _wsClient: null });
        };
    },
}));
