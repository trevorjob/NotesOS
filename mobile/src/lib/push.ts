import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import Constants from 'expo-constants';
import { router } from 'expo-router';
import { api } from '@/lib/api';
import { getStoredItem, setStoredItem, deleteStoredItem } from '@/lib/secureStorage';
import { routeForNotification } from '@/lib/notificationRouting';
import type { NotificationItem } from '@/lib/notifications';

// OS push (Lane 2, notifications-plan.md Phase C). Two halves:
//   1. registerForPushNotifications() — permission + Expo token + POST /notifications/devices.
//      Call after login and on app-start when already authed.
//   2. initNotificationTapHandling() — foreground banner policy + tap → deep link via
//      meta_data (routeForNotification, shared with the in-app feed's own tap handler so
//      both lanes land identically). Call once at root.

const PUSH_TOKEN_CACHE_KEY = 'notesos.pushToken';

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    // Foreground: the WS lane (NotificationsProvider) already surfaces this live in the
    // feed + badge, so suppress the OS banner to avoid a double-surface (see
    // notifications-plan.md §2 "Foreground de-dup"). Background/killed: this handler
    // never runs — the OS renders the banner itself from the raw push payload.
    shouldShowBanner: false,
    shouldShowList: true,
    shouldPlaySound: false,
    shouldSetBadge: true,
  }),
});

function projectId(): string | undefined {
  return Constants.expoConfig?.extra?.eas?.projectId as string | undefined;
}

export async function registerForPushNotifications(): Promise<void> {
  // Simulators/emulators have no push capability; skip rather than throw.
  if (!Device.isDevice) return;

  const id = projectId();
  if (!id) return; // No EAS project configured yet — see notifications-plan.md §5 (owner action).

  const existing = await Notifications.getPermissionsAsync();
  let finalStatus = existing.status;
  if (finalStatus !== 'granted') {
    const requested = await Notifications.requestPermissionsAsync();
    finalStatus = requested.status;
  }
  if (finalStatus !== 'granted') return;

  if (Platform.OS === 'android') {
    await Notifications.setNotificationChannelAsync('default', {
      name: 'default',
      importance: Notifications.AndroidImportance.DEFAULT,
    });
  }

  const { data: token } = await Notifications.getExpoPushTokenAsync({ projectId: id });
  await api.post('/api/notifications/devices', { token, platform: Platform.OS });
  await setStoredItem(PUSH_TOKEN_CACHE_KEY, token);
}

/** Unregister this device's push token (sign-out, account delete). Best-effort. */
export async function unregisterPushToken(): Promise<void> {
  const token = await getStoredItem(PUSH_TOKEN_CACHE_KEY);
  if (!token) return;
  try {
    await api.delete(`/api/notifications/devices/${encodeURIComponent(token)}`);
  } catch {
    // Best-effort — a stray server-side row is harmless (next push to a dead token
    // self-prunes via DeviceNotRegistered).
  } finally {
    await deleteStoredItem(PUSH_TOKEN_CACHE_KEY);
  }
}

function handleTap(response: Notifications.NotificationResponse): void {
  // The Expo push payload's `data` is exactly the `data` object create_and_push_notification's
  // Lane 2 send builds — meta_data plus a stamped `type` (see services/push.py) — so it
  // carries what routeForNotification needs, same as the in-app feed's own NotificationItem.
  const data = (response.notification.request.content.data ?? {}) as Partial<NotificationItem> &
    Record<string, unknown>;
  const destination = routeForNotification({
    type: (data.type as NotificationItem['type']) ?? 'GENERAL',
    meta_data: data,
  });
  if (destination) router.push(destination);
}

/** Wire the tap→deep-link listener + handle a cold-start launch from a notification. */
export function initNotificationTapHandling(): () => void {
  const subscription = Notifications.addNotificationResponseReceivedListener(handleTap);

  void Notifications.getLastNotificationResponseAsync().then((response) => {
    if (response) handleTap(response);
  });

  return () => subscription.remove();
}
