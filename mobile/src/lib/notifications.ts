import { api } from '@/lib/api';

// Client for /api/notifications — the in-app feed (list/read/delete) and the habit-loop
// preference toggles. The live-push counterpart is lib/userSocket.ts (WS /ws/user/{id}).

// Mirrors the backend NotificationType enum. Kept as a union of known values plus a
// string fallback so an unrecognised server type degrades to the generic renderer.
export type NotificationType =
  | 'DECAY_NUDGE'
  | 'AI_SUMMARY_READY'
  | 'RESOURCE_UPLOADED'
  | 'CLASSMATE_JOINED'
  | 'INVITE_ACCEPTED'
  | 'TEST_GRADED'
  | 'GENERAL'
  | (string & {});

export interface NotificationItem {
  id: string;
  type: NotificationType;
  title: string;
  body: string;
  is_read: boolean;
  meta_data: Record<string, unknown> | null;
  created_at: string;
}

export interface NotificationPage {
  notifications: NotificationItem[];
  total: number;
  has_more: boolean;
}

export async function fetchNotifications(
  { limit = 20, offset = 0 }: { limit?: number; offset?: number } = {}
): Promise<NotificationPage> {
  const { data } = await api.get('/api/notifications', { params: { limit, offset } });
  return data;
}

export async function fetchUnreadCount(): Promise<number> {
  const { data } = await api.get('/api/notifications/unread-count');
  return data.count ?? 0;
}

export async function markNotificationRead(id: string): Promise<void> {
  await api.patch(`/api/notifications/${id}/read`);
}

export async function markAllNotificationsRead(): Promise<void> {
  await api.patch('/api/notifications/read-all');
}

export async function deleteNotification(id: string): Promise<void> {
  await api.delete(`/api/notifications/${id}`);
}

export async function deleteAllNotifications(): Promise<void> {
  await api.delete('/api/notifications');
}

// Notification preferences — the habit-loop nudges (§15.4). The "daily decay digest"
// toggle on the settings screen lives here (its own table), NOT in the generic
// /me/preferences dict. Both loops default on. Maps to /api/notifications/preferences.

export interface NotificationPreferences {
  digest_enabled: boolean;
  recognition_enabled: boolean;
  last_digest_at: string | null;
}

export async function fetchNotificationPreferences(): Promise<NotificationPreferences> {
  const { data } = await api.get('/api/notifications/preferences');
  return data;
}

export async function updateNotificationPreferences(
  patch: { digest_enabled?: boolean; recognition_enabled?: boolean }
): Promise<void> {
  await api.patch('/api/notifications/preferences', patch);
}
