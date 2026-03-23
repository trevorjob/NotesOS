/**
 * NotesOS - Notification Store
 * Real-time notifications via WebSocket + REST polling
 */

import { create } from 'zustand';
import { api } from '@/lib/api';
import { WebSocketClient } from '@/lib/websocket';

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
    message: string;
    variant: 'info' | 'success' | 'error';
}

interface NotificationState {
    notifications: AppNotification[];
    unreadCount: number;
    toasts: Toast[];
    _wsClient: WebSocketClient | null;

    fetchUnreadCount: () => Promise<void>;
    fetchNotifications: () => Promise<void>;
    addToast: (message: string, variant?: Toast['variant']) => void;
    dismissToast: (id: string) => void;
    markRead: (id: string) => Promise<void>;
    markAllRead: () => Promise<void>;
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

    addToast: (message, variant = 'info') => {
        const id = Math.random().toString(36).slice(2);
        set((s) => ({ toasts: [...s.toasts.slice(-2), { id, message, variant }] }));
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
                    // Fires once when the whole test is graded (backend guarantees this).
                    // The test page handles navigation; we just update the bell count.
                    fetchUnreadCount();
                } else if (msg.type === 'processing_status') {
                    if (msg.status === 'completed') {
                        addToast('Resource processed and ready.', 'success');
                    } else if (msg.status === 'failed') {
                        addToast('Resource processing failed.', 'error');
                    }
                } else if (msg.type === 'fact_check:complete') {
                    addToast('AI summary ready for your resource.', 'info');
                } else if ((msg as any).type === 'notification') {
                    const n = (msg as any).data as AppNotification;
                    if (n?.id) {
                        pushNotification(n);
                        addToast(n.title, 'info');
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
