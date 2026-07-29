import { api } from '@/lib/api';

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
