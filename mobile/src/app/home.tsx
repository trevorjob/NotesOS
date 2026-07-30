import React, { useCallback, useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router, useFocusEffect } from 'expo-router';
import { useTheme } from '@/theme/ThemeProvider';
import { useQuickSwitcher } from '@/components/nav/QuickSwitcherContext';
import { Button } from '@/components/ui/Button';
import { Divider } from '@/components/ui/Divider';
import { IconButton } from '@/components/ui/IconButton';
import { CoursePickerSheet } from '@/components/course/CoursePickerSheet';
import { MyCourse, fetchMyCourses } from '@/lib/courses';
import { NextAction, fetchNextAction } from '@/lib/retrieval';

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

const ACTION_LEAD: Record<NextAction['kind'], string> = {
  review: 'Fading — worth firming up',
  calibration: 'Sure but missed — recheck',
  dump: 'Fresh read — dump it while warm',
  new: 'New — a quick pretest primes it',
  get_ahead: 'All caught up — get ahead',
};

export default function HomeScreen() {
  const { c, font, size, space, trackingUtility } = useTheme();
  const { openSwitcher } = useQuickSwitcher();

  const [courses, setCourses] = useState<MyCourse[]>([]);
  const [action, setAction] = useState<NextAction | null>(null);
  const [actionLoading, setActionLoading] = useState(true);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerPurpose, setPickerPurpose] = useState<'capture' | 'test'>('capture');

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
      (async () => {
        try {
          const next = await fetchNextAction();
          if (alive) setAction(next);
        } catch {
          if (alive) setAction(null);
        } finally {
          if (alive) setActionLoading(false);
        }
      })();
      return () => {
        alive = false;
      };
    }, [])
  );

  // The engine already chose the mode; hand retrieval the topic + first target concept so it
  // opens straight into the right challenge (concept modes challenge it; dump/recap ignore it).
  const startAction = () => {
    if (!action) return;
    router.push({
      pathname: '/retrieval',
      params: {
        topicId: action.topic_id,
        courseId: action.course_id,
        mode: action.mode,
        ...(action.concept_ids[0] ? { conceptId: action.concept_ids[0] } : {}),
      },
    });
  };

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
            onPress={() => {
              setPickerPurpose('capture');
              setPickerOpen(true);
            }}
            style={{ flex: 1 }}
          />
        </View>

        <Pressable
          onPress={() => {
            setPickerPurpose('test');
            setPickerOpen(true);
          }}
          style={{ paddingHorizontal: space.gutterPage, paddingTop: 12, minHeight: 44, justifyContent: 'center' }}
        >
          <Text style={{ color: c.confirm, textDecorationLine: 'underline', fontSize: size.bodySm }}>✎ Build a practice test</Text>
        </Pressable>

        {/* Retrieval hero — the engine picks the single highest-value thing to study now. */}
        <View style={{ flex: 1, justifyContent: 'center', paddingHorizontal: space.gutterPage, gap: 14 }}>
          {actionLoading ? (
            <ActivityIndicator color={c.ink} />
          ) : action ? (
            <>
              <Text style={[utilityText, { color: c.stateFading }]}>{ACTION_LEAD[action.kind]}</Text>
              <Text style={{ fontFamily: font.display, fontSize: size.display1, lineHeight: size.display1 * 1.15, color: c.ink }}>
                {action.topic_title}
              </Text>
              <Text style={{ fontSize: size.bodySm, color: c.inkSecondary }}>{`${action.reason} · about ${action.est_minutes} min`}</Text>
              <Button label="Start review" onPress={startAction} style={{ marginTop: 10 }} />
            </>
          ) : (
            <>
              <Text style={{ fontFamily: font.display, fontSize: size.display2, lineHeight: size.display2 * 1.15, color: c.ink }}>
                Nothing due right now
              </Text>
              <Text style={{ fontSize: size.bodySm, color: c.inkSecondary }}>
                Add material or open a note and tap a concept to start a review.
              </Text>
            </>
          )}
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
          const pathname = pickerPurpose === 'test' ? '/testbuilder' : '/capture';
          router.push({ pathname, params: { courseId } });
        }}
      />
    </SafeAreaView>
  );
}
