import React from 'react';
import { Pressable, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { useTheme } from '@/theme/ThemeProvider';
import { useQuickSwitcher } from '@/components/nav/QuickSwitcherContext';
import { Button } from '@/components/ui/Button';
import { Divider } from '@/components/ui/Divider';
import { IconButton } from '@/components/ui/IconButton';

export default function HomeScreen() {
  const { c, font, size, space, trackingUtility } = useTheme();
  const { openSwitcher } = useQuickSwitcher();

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
      <View style={{ flex: 1 }}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: space.gutterPage, paddingTop: 18 }}>
          <Text
            style={{
              fontFamily: font.utility,
              fontSize: size.utility,
              letterSpacing: trackingUtility(size.utility),
              textTransform: 'uppercase',
              color: c.inkTertiary,
            }}
          >
            Good evening
          </Text>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <IconButton icon={<Text style={{ color: c.ink, fontSize: 16 }}>⌕</Text>} label="Jump to a course, topic, or note" onPress={openSwitcher} />
            <IconButton icon={<Text style={{ color: c.ink, fontSize: 16 }}>●</Text>} label="Notifications" onPress={() => router.push('/notifications')} />
            <IconButton icon={<Text style={{ color: c.ink, fontSize: 16 }}>⚙</Text>} label="Settings" onPress={() => router.push('/settings')} />
          </View>
        </View>

        <View style={{ flexDirection: 'row', gap: 10, paddingHorizontal: space.gutterPage, paddingTop: 16 }}>
          <Button
            label="Browse courses"
            variant="secondary"
            icon={<Text style={{ color: c.ink }}>▦</Text>}
            onPress={() => router.push('/courses')}
            style={{ flex: 1 }}
          />
          <Button
            label="Add material"
            variant="secondary"
            icon={<Text style={{ color: c.ink, fontSize: 18, lineHeight: 18 }}>+</Text>}
            onPress={() => router.push('/capture')}
            style={{ flex: 1 }}
          />
        </View>

        <View style={{ flex: 1, justifyContent: 'center', paddingHorizontal: space.gutterPage, gap: 14 }}>
          <Text
            style={{
              fontFamily: font.utility,
              fontSize: size.utility,
              letterSpacing: trackingUtility(size.utility),
              textTransform: 'uppercase',
              color: c.stateFading,
            }}
          >
            3 concepts slipping in Cellular Respiration
          </Text>
          <Text style={{ fontFamily: font.display, fontSize: size.display1, lineHeight: size.display1 * 1.15, color: c.ink }}>
            Firm up the electron transport chain
          </Text>
          <Text style={{ fontSize: size.bodySm, color: c.inkSecondary }}>
            About 5 minutes · quiz + one worked recall
          </Text>
          <Button label="Start review" onPress={() => router.push('/retrieval')} style={{ marginTop: 10 }} />
        </View>

        <View style={{ paddingHorizontal: space.gutterPage, paddingBottom: 24 }}>
          <Divider spacing={0} />
          <View style={{ flexDirection: 'row', gap: 20, marginTop: 16, marginBottom: 16 }}>
            <Pressable onPress={() => router.push('/note')} style={{ minHeight: 44, justifyContent: 'center' }}>
              <Text style={{ color: c.confirm, textDecorationLine: 'underline', fontSize: size.bodySm }}>
                Open Cellular Respiration note
              </Text>
            </Pressable>
            <Pressable onPress={() => router.push('/testbuilder')} style={{ minHeight: 44, justifyContent: 'center' }}>
              <Text style={{ color: c.confirm, textDecorationLine: 'underline', fontSize: size.bodySm }}>
                Build a practice test
              </Text>
            </Pressable>
          </View>
          <Text style={{ fontSize: size.bodySm, color: c.inkTertiary }}>
            2 classmates used your note this week
          </Text>
        </View>
      </View>
    </SafeAreaView>
  );
}
