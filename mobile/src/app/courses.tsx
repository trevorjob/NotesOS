import React, { useCallback, useMemo, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router, useFocusEffect } from 'expo-router';
import { isAxiosError } from 'axios';
import { useTheme } from '@/theme/ThemeProvider';
import { useQuickSwitcher } from '@/components/nav/QuickSwitcherContext';
import { IconButton } from '@/components/ui/IconButton';
import { MyCourse, MyCourseTopic, fetchMyCourses } from '@/lib/courses';

interface TermGroup {
  term: string;
  courses: MyCourse[];
}

const UNFILED_LABEL = 'Your courses';

function readError(err: unknown): string {
  if (isAxiosError(err) && typeof err.response?.data?.detail === 'string') return err.response.data.detail;
  return 'Couldn’t load your courses. Pull to try again.';
}

function courseActivity(course: MyCourse): string {
  if (course.last_studied) return `Last studied ${course.last_studied.topic_name}`;
  if (course.member_count > 1) return `${course.member_count} classmates`;
  return 'Just you so far';
}

function topicSubtitle(topic: MyCourseTopic): string {
  return topic.week_number != null ? `Week ${topic.week_number}` : 'Topic';
}

export default function CoursesScreen() {
  const { c, font, size, space, trackingUtility } = useTheme();
  const { openSwitcher } = useQuickSwitcher();

  const [courses, setCourses] = useState<MyCourse[]>([]);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useFocusEffect(
    useCallback(() => {
      let alive = true;
      (async () => {
        try {
          const list = await fetchMyCourses();
          if (!alive) return;
          setCourses(list);
          setError(null);
        } catch (err) {
          if (alive) setError(readError(err));
        } finally {
          if (alive) setLoading(false);
        }
      })();
      return () => {
        alive = false;
      };
    }, [])
  );

  const groups = useMemo<TermGroup[]>(() => {
    const byTerm = new Map<string, MyCourse[]>();
    for (const course of courses) {
      const label = course.term_label ?? UNFILED_LABEL;
      byTerm.set(label, [...(byTerm.get(label) ?? []), course]);
    }
    return [...byTerm.entries()].map(([term, list]) => ({ term, courses: list }));
  }, [courses]);

  const toggle = (courseId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(courseId)) next.delete(courseId);
      else next.add(courseId);
      return next;
    });
  };

  const openNote = (topicId: string, courseId: string) =>
    router.push({ pathname: '/note', params: { topicId, courseId } });

  const footerLink = (label: string, onPress: () => void) => (
    <Pressable onPress={onPress} style={{ minHeight: 44, justifyContent: 'center' }}>
      <Text style={{ color: c.confirm, textDecorationLine: 'underline', fontSize: size.bodySm }}>{label}</Text>
    </Pressable>
  );

  const utilityText = {
    fontFamily: font.utility,
    fontSize: size.caption,
    letterSpacing: trackingUtility(size.caption),
    textTransform: 'uppercase' as const,
    color: c.inkTertiary,
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
      <View style={{ flex: 1 }}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: space.gutterPage, paddingTop: 18, paddingBottom: 10 }}>
          <Text style={{ fontFamily: font.display, fontSize: size.display2, color: c.ink }}>Your courses</Text>
          <IconButton icon={<Text style={{ color: c.ink, fontSize: 16 }}>⌕</Text>} label="Jump to a course, topic, or note" onPress={openSwitcher} />
        </View>

        {loading ? (
          <View style={{ paddingTop: 60, alignItems: 'center', gap: 14 }}>
            <ActivityIndicator color={c.ink} />
            <Text style={{ color: c.inkSecondary, fontSize: size.body }}>Loading your courses…</Text>
          </View>
        ) : (
          <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingHorizontal: space.gutterPage, paddingBottom: 20 }}>
            {error && <Text style={{ color: c.stateShaky, fontSize: size.bodySm, marginTop: 14 }}>{error}</Text>}

            {!error && courses.length === 0 && (
              <Text style={{ color: c.inkTertiary, fontSize: size.body, paddingVertical: 24 }}>
                No courses yet — join or create one below.
              </Text>
            )}

            {groups.map((group) => (
              <View key={group.term} style={{ marginBottom: 20 }}>
                <Text style={[utilityText, { marginTop: 14, marginBottom: 4 }]}>{group.term}</Text>

                {group.courses.map((course) => {
                  const isOpen = expanded.has(course.id);
                  return (
                    <View key={course.id}>
                      <Pressable
                        onPress={() => toggle(course.id)}
                        style={{ paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: c.paperEdge, minHeight: 44, flexDirection: 'row', alignItems: 'center', gap: 12 }}
                      >
                        <Text style={{ color: c.inkTertiary, fontSize: 14, width: 14 }}>{isOpen ? '▾' : '▸'}</Text>
                        <View style={{ flex: 1, gap: 2 }}>
                          <Text style={{ fontWeight: '600', fontSize: 17, color: c.ink }}>{course.name}</Text>
                          <View style={{ flexDirection: 'row', gap: 10 }}>
                            <Text style={{ fontSize: size.caption, color: c.inkTertiary }}>{course.code}</Text>
                            <Text style={{ fontSize: size.caption, color: c.inkSecondary }}>{courseActivity(course)}</Text>
                          </View>
                        </View>
                      </Pressable>

                      {isOpen && (
                        <View style={{ paddingLeft: 26, paddingBottom: 6 }}>
                          {course.topics.length === 0 ? (
                            <Pressable
                              onPress={() => router.push({ pathname: '/capture', params: { courseId: course.id, mode: 'outline' } })}
                              style={{ paddingVertical: 12, minHeight: 44, justifyContent: 'center' }}
                            >
                              <Text style={{ color: c.confirm, fontSize: size.bodySm }}>
                                No topics yet — set up from your syllabus
                              </Text>
                            </Pressable>
                          ) : (
                            course.topics.map((topic) => (
                              <Pressable
                                key={topic.id}
                                onPress={() => openNote(topic.id, course.id)}
                                style={{ paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: c.paperEdge, minHeight: 44, gap: 2 }}
                              >
                                <Text style={{ fontSize: 16, color: c.ink }}>{topic.title}</Text>
                                <Text style={{ fontSize: size.caption, color: c.inkTertiary }}>{topicSubtitle(topic)}</Text>
                              </Pressable>
                            ))
                          )}
                          <Pressable
                            onPress={() => router.push({ pathname: '/capture', params: { courseId: course.id } })}
                            style={{ paddingVertical: 12, minHeight: 44, justifyContent: 'center' }}
                          >
                            <Text style={{ color: c.confirm, textDecorationLine: 'underline', fontSize: size.bodySm }}>+ Add material</Text>
                          </Pressable>
                        </View>
                      )}
                    </View>
                  );
                })}
              </View>
            ))}
          </ScrollView>
        )}

        <View style={{ padding: space.gutterPage, borderTopWidth: 1, borderTopColor: c.paperEdge, flexDirection: 'row', gap: 20, flexWrap: 'wrap' }}>
          {footerLink('Create a course', () => router.push('/coursecreate'))}
          {footerLink('Join with a code', () => router.push('/coursejoin'))}
          {footerLink('Discover', () => router.push('/discovery'))}
        </View>
      </View>
    </SafeAreaView>
  );
}
