import React, { useCallback, useMemo, useState } from 'react';
import { Pressable, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router, useFocusEffect } from 'expo-router';
import { useTheme } from '@/theme/ThemeProvider';
import { useQuickSwitcher } from '@/components/nav/QuickSwitcherContext';
import { Button } from '@/components/ui/Button';
import { Divider } from '@/components/ui/Divider';
import { IconButton } from '@/components/ui/IconButton';
import { CoursePickerSheet } from '@/components/course/CoursePickerSheet';
import { MyCourse, fetchMyCourses } from '@/lib/courses';

interface RecentNote {
  topicId: string;
  courseId: string;
  title: string;
  courseCode: string;
}

function recentNotesFrom(courses: MyCourse[]): RecentNote[] {
  return courses
    .filter((course) => course.last_studied)
    .map((course) => ({ course, ls: course.last_studied! }))
    .sort((a, b) => (a.ls.studied_at < b.ls.studied_at ? 1 : -1))
    .slice(0, 3)
    .map(({ course, ls }) => ({
      topicId: ls.topic_id,
      courseId: course.id,
      title: ls.topic_name,
      courseCode: course.code,
    }));
}

export default function HomeScreen() {
  const { c, font, size, space, trackingUtility } = useTheme();
  const { openSwitcher } = useQuickSwitcher();

  const [courses, setCourses] = useState<MyCourse[]>([]);
  const [pickerOpen, setPickerOpen] = useState(false);

  useFocusEffect(
    useCallback(() => {
      let alive = true;
      (async () => {
        try {
          const list = await fetchMyCourses();
          if (alive) setCourses(list);
        } catch {
          if (alive) setCourses([]);
        }
      })();
      return () => {
        alive = false;
      };
    }, [])
  );

  const recents = useMemo(() => recentNotesFrom(courses), [courses]);

  const utilityText = {
    fontFamily: font.utility,
    fontSize: size.utility,
    letterSpacing: trackingUtility(size.utility),
    textTransform: 'uppercase' as const,
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
      <View style={{ flex: 1 }}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: space.gutterPage, paddingTop: 18 }}>
          <Text style={[utilityText, { color: c.inkTertiary }]}>Good evening</Text>
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
            onPress={() => setPickerOpen(true)}
            style={{ flex: 1 }}
          />
        </View>

        {/* Retrieval hero — still mock; wired in the retrieval pass (§2.7). */}
        <View style={{ flex: 1, justifyContent: 'center', paddingHorizontal: space.gutterPage, gap: 14 }}>
          <Text style={[utilityText, { color: c.stateFading }]}>3 concepts slipping in Cellular Respiration</Text>
          <Text style={{ fontFamily: font.display, fontSize: size.display1, lineHeight: size.display1 * 1.15, color: c.ink }}>
            Firm up the electron transport chain
          </Text>
          <Text style={{ fontSize: size.bodySm, color: c.inkSecondary }}>About 5 minutes · quiz + one worked recall</Text>
          <Button label="Start review" onPress={() => router.push('/retrieval')} style={{ marginTop: 10 }} />
        </View>

        <View style={{ paddingHorizontal: space.gutterPage, paddingBottom: 24 }}>
          <Divider spacing={0} />
          {recents.length > 0 ? (
            <View style={{ marginTop: 16, gap: 4 }}>
              <Text style={[utilityText, { color: c.inkTertiary, marginBottom: 6 }]}>Jump back in</Text>
              {recents.map((note) => (
                <Pressable
                  key={note.topicId}
                  onPress={() => router.push({ pathname: '/note', params: { topicId: note.topicId, courseId: note.courseId } })}
                  style={{ paddingVertical: 10, minHeight: 44, justifyContent: 'center' }}
                >
                  <Text style={{ color: c.confirm, fontSize: size.body }}>{note.title}</Text>
                  <Text style={{ color: c.inkTertiary, fontSize: size.caption }}>{note.courseCode}</Text>
                </Pressable>
              ))}
            </View>
          ) : (
            <Text style={{ marginTop: 16, color: c.inkTertiary, fontSize: size.bodySm }}>
              Your recent notes will show up here once you start studying.
            </Text>
          )}
        </View>
      </View>

      <CoursePickerSheet
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        onSelect={(courseId) => {
          setPickerOpen(false);
          router.push({ pathname: '/capture', params: { courseId } });
        }}
      />
    </SafeAreaView>
  );
}
