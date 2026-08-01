import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, Alert, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router, useFocusEffect } from 'expo-router';
import { useTheme } from '@/theme/ThemeProvider';
import { useNotifications } from '@/components/notifications/NotificationsProvider';
import {
  deleteNotification,
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  NotificationItem,
} from '@/lib/notifications';
import { routeForNotification } from '@/lib/notificationRouting';

const PAGE_SIZE = 20;

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '';
  const minutes = Math.floor((Date.now() - then) / 60_000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return 'Yesterday';
  if (days < 7) return `${days} days ago`;
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

function groupFor(iso: string): 'Today' | 'Earlier' {
  const then = new Date(iso);
  const now = new Date();
  const sameDay =
    then.getFullYear() === now.getFullYear() && then.getMonth() === now.getMonth() && then.getDate() === now.getDate();
  return sameDay ? 'Today' : 'Earlier';
}

export default function NotificationsScreen() {
  const { c, font, size, space, trackingUtility } = useTheme();
  const { refreshUnreadCount, markAllReadLocally, markOneReadLocally, subscribeToLive } = useNotifications();

  const [items, setItems] = useState<NotificationItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const page = await fetchNotifications({ limit: PAGE_SIZE, offset: 0 });
      setItems(page.notifications);
      setHasMore(page.has_more);
    } catch {
      setError("Couldn't load notifications.");
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load])
  );

  // Live-pushed notifications (Lane 1, see notifications-plan.md) prepend as they arrive.
  useEffect(() => subscribeToLive((item) => setItems((prev) => [item, ...prev])), [subscribeToLive]);

  const loadMore = async () => {
    if (loadingMore || !hasMore) return;
    setLoadingMore(true);
    try {
      const page = await fetchNotifications({ limit: PAGE_SIZE, offset: items.length });
      setItems((prev) => [...prev, ...page.notifications]);
      setHasMore(page.has_more);
    } catch {
      // Silent — the "Load more" button just stays tappable to retry.
    } finally {
      setLoadingMore(false);
    }
  };

  const markAllRead = async () => {
    setItems((prev) => prev.map((item) => ({ ...item, is_read: true })));
    markAllReadLocally();
    try {
      await markAllNotificationsRead();
    } catch {
      void load(); // Rollback to server truth on failure.
    }
  };

  const openItem = async (item: NotificationItem) => {
    if (!item.is_read) {
      setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, is_read: true } : i)));
      markOneReadLocally();
      markNotificationRead(item.id).catch(() => {
        void refreshUnreadCount();
      });
    }
    const destination = routeForNotification(item);
    if (destination) router.push(destination);
  };

  const removeItem = (item: NotificationItem) => {
    Alert.alert('Delete notification?', item.title, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: () => {
          setItems((prev) => prev.filter((i) => i.id !== item.id));
          if (!item.is_read) markOneReadLocally();
          deleteNotification(item.id).catch(() => void load());
        },
      },
    ]);
  };

  const groups: ('Today' | 'Earlier')[] = ['Today', 'Earlier'];

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
      <View
        style={{
          paddingHorizontal: space.gutterPage,
          paddingTop: 18,
          paddingBottom: 10,
          flexDirection: 'row',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
        }}
      >
        <View>
          <Pressable onPress={() => router.back()} style={{ minHeight: 44, justifyContent: 'center' }}>
            <Text style={{ color: c.inkSecondary, fontSize: size.bodySm }}>← Home</Text>
          </Pressable>
          <Text style={{ fontFamily: font.display, fontSize: size.display2, color: c.ink, marginTop: 4 }}>
            Notifications
          </Text>
        </View>
        {items.some((i) => !i.is_read) && (
          <Pressable onPress={markAllRead} style={{ minHeight: 44, justifyContent: 'center' }}>
            <Text style={{ color: c.confirm, textDecorationLine: 'underline', fontSize: size.bodySm }}>
              Mark all read
            </Text>
          </Pressable>
        )}
      </View>

      {loading ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <ActivityIndicator color={c.confirm} />
        </View>
      ) : error ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: space.gutterPage }}>
          <Text style={{ color: c.inkSecondary, textAlign: 'center' }}>{error}</Text>
          <Pressable onPress={load} style={{ marginTop: 12, minHeight: 44, justifyContent: 'center' }}>
            <Text style={{ color: c.confirm, textDecorationLine: 'underline' }}>Try again</Text>
          </Pressable>
        </View>
      ) : items.length === 0 ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: space.gutterPage }}>
          <Text style={{ color: c.inkSecondary, textAlign: 'center' }}>Nothing yet — you&apos;ll see study nudges and updates here.</Text>
        </View>
      ) : (
        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingHorizontal: space.gutterPage, paddingBottom: 20 }}>
          {groups.map((g) => {
            const groupItems = items.filter((item) => groupFor(item.created_at) === g);
            if (groupItems.length === 0) return null;
            return (
              <View key={g}>
                <Text
                  style={{
                    fontFamily: font.utility,
                    fontSize: size.caption,
                    letterSpacing: trackingUtility(size.caption),
                    textTransform: 'uppercase',
                    color: c.inkTertiary,
                    marginTop: 14,
                    marginBottom: 4,
                  }}
                >
                  {g}
                </Text>
                {groupItems.map((item) => (
                  <Pressable
                    key={item.id}
                    onPress={() => openItem(item)}
                    onLongPress={() => removeItem(item)}
                    style={{
                      flexDirection: 'row',
                      gap: 10,
                      paddingVertical: 12,
                      borderBottomWidth: 1,
                      borderBottomColor: c.paperEdge,
                      minHeight: 44,
                      alignItems: 'flex-start',
                    }}
                  >
                    <View
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: 4,
                        backgroundColor: !item.is_read ? c.confirm : 'transparent',
                        marginTop: 6,
                        flexShrink: 0,
                      }}
                    />
                    <View style={{ flex: 1 }}>
                      <Text style={{ color: c.ink, fontWeight: !item.is_read ? '600' : '400' }}>{item.title}</Text>
                      <Text style={{ color: c.inkSecondary, marginTop: 2 }}>{item.body}</Text>
                      <Text style={{ fontSize: size.caption, color: c.inkTertiary, marginTop: 2 }}>
                        {relativeTime(item.created_at)}
                      </Text>
                    </View>
                  </Pressable>
                ))}
              </View>
            );
          })}

          {hasMore && (
            <Pressable onPress={loadMore} style={{ paddingVertical: 16, alignItems: 'center' }}>
              {loadingMore ? (
                <ActivityIndicator color={c.confirm} />
              ) : (
                <Text style={{ color: c.confirm, textDecorationLine: 'underline', fontSize: size.bodySm }}>
                  Load more
                </Text>
              )}
            </Pressable>
          )}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}
