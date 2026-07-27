import React, { useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { useTheme } from '@/theme/ThemeProvider';

interface NotificationItem {
  group: string;
  unread: boolean;
  kind: string;
  text: string;
  time: string;
}

const ITEMS: NotificationItem[] = [
  { group: 'Today', unread: true, kind: 'decay', text: 'Good time to firm up the Krebs cycle — 5 min', time: '2h ago' },
  { group: 'Today', unread: true, kind: 'recognition', text: 'Ada used your Cellular Respiration note', time: '4h ago' },
  { group: 'Earlier', unread: false, kind: 'info', text: 'Photosynthesis note finished synthesizing', time: 'Yesterday' },
  { group: 'Earlier', unread: false, kind: 'recognition', text: '2 classmates joined Organic Chemistry II', time: '2 days ago' },
];

const GROUPS = ['Today', 'Earlier'];

type ReadMap = Record<string, boolean>;

export default function NotificationsScreen() {
  const { c, font, size, space, trackingUtility } = useTheme();
  const [read, setRead] = useState<ReadMap>({});

  const markRead = (key: string) => setRead((r) => ({ ...r, [key]: true }));
  const markAllRead = () => setRead({ all: true });

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
      <View style={{ paddingHorizontal: space.gutterPage, paddingTop: 18, paddingBottom: 10, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <View>
          <Pressable onPress={() => router.back()} style={{ minHeight: 44, justifyContent: 'center' }}>
            <Text style={{ color: c.inkSecondary, fontSize: size.bodySm }}>← Home</Text>
          </Pressable>
          <Text style={{ fontFamily: font.display, fontSize: size.display2, color: c.ink, marginTop: 4 }}>Notifications</Text>
        </View>
        <Pressable onPress={markAllRead} style={{ minHeight: 44, justifyContent: 'center' }}>
          <Text style={{ color: c.confirm, textDecorationLine: 'underline', fontSize: size.bodySm }}>Mark all read</Text>
        </Pressable>
      </View>

      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingHorizontal: space.gutterPage, paddingBottom: 20 }}>
        {GROUPS.map((g) => (
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
            {ITEMS.filter((item) => item.group === g).map((item, i) => {
              const key = g + i;
              const isUnread = item.unread && !read.all;
              return (
                <Pressable
                  key={key}
                  onPress={() => markRead(key)}
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
                  <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: isUnread ? c.confirm : 'transparent', marginTop: 6, flexShrink: 0 }} />
                  <View style={{ flex: 1 }}>
                    <Text style={{ color: c.ink, fontWeight: isUnread ? '600' : '400' }}>{item.text}</Text>
                    <Text style={{ fontSize: size.caption, color: c.inkTertiary }}>{item.time}</Text>
                  </View>
                </Pressable>
              );
            })}
          </View>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}
