import React, { useCallback, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { isAxiosError } from 'axios';
import { useTheme } from '@/theme/ThemeProvider';
import { useQuickSwitcher } from '@/components/nav/QuickSwitcherContext';
import { IconButton } from '@/components/ui/IconButton';
import { CourseDetail, CourseTopic, fetchCourseTopics } from '@/lib/topics';

function readError(err: unknown): string {
  if (isAxiosError(err) && typeof err.response?.data?.detail === 'string') {
    return err.response.data.detail;
  }
  return 'Couldn’t load this course. Go back and try again.';
}

// Secondary line for a topic row — description if the course author wrote one,
// otherwise the week it maps to, otherwise nothing to say yet.
function topicSubtitle(topic: CourseTopic): string {
  if (topic.description) return topic.description;
  if (topic.week_number != null) return `Week ${topic.week_number}`;
  return 'No description yet';
}

export default function TopicsScreen() {
  const { c, font, size, space, trackingUtility } = useTheme();
  const { openSwitcher } = useQuickSwitcher();
  const { courseId } = useLocalSearchParams<{ courseId?: string }>();

  const [course, setCourse] = useState<CourseDetail | null>(null);
  const [topics, setTopics] = useState<CourseTopic[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Refetch on focus so returning from the capture modal shows newly added topics.
  useFocusEffect(
    useCallback(() => {
      if (!courseId) {
        setError('No course selected.');
        setLoading(false);
        return;
      }
      let alive = true;
      (async () => {
        try {
          const { course: detail, topics: list } = await fetchCourseTopics(courseId);
          if (!alive) return;
          setCourse(detail);
          setTopics(list);
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
    }, [courseId])
  );

  const sectionLabel = (label: string) => (
    <Text
      style={{
        fontFamily: font.utility,
        fontSize: size.caption,
        letterSpacing: trackingUtility(size.caption),
        textTransform: 'uppercase',
        color: c.inkTertiary,
        marginTop: 10,
        marginBottom: 4,
      }}
    >
      {label}
    </Text>
  );

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
      <View style={{ flex: 1 }}>
        <View style={{ paddingHorizontal: space.gutterPage, paddingTop: 18, paddingBottom: 10 }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <View style={{ flex: 1, paddingRight: 12 }}>
              <Pressable onPress={() => router.back()} style={{ minHeight: 44, justifyContent: 'center' }}>
                <Text style={{ color: c.inkSecondary, fontSize: size.bodySm }}>← Courses</Text>
              </Pressable>
              <Text style={{ fontFamily: font.display, fontSize: size.display2, color: c.ink, marginTop: 4 }}>
                {course?.name ?? 'Course'}
              </Text>
              {course?.code ? (
                <Text style={{ marginTop: 6, fontSize: size.bodySm, color: c.inkTertiary }}>{course.code}</Text>
              ) : null}
            </View>
            <IconButton icon={<Text style={{ color: c.ink, fontSize: 16 }}>⌕</Text>} label="Switch" onPress={openSwitcher} />
          </View>
        </View>

        {loading ? (
          <View style={{ paddingTop: 60, alignItems: 'center', gap: 14 }}>
            <ActivityIndicator color={c.ink} />
            <Text style={{ color: c.inkSecondary, fontSize: size.body }}>Loading topics…</Text>
          </View>
        ) : (
          <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingHorizontal: space.gutterPage, paddingBottom: 20 }}>
            {error && (
              <Text style={{ color: c.stateShaky, fontSize: size.bodySm, marginTop: 14 }}>{error}</Text>
            )}

            {!error && topics.length === 0 && (
              <Text style={{ color: c.inkTertiary, fontSize: size.body, paddingVertical: 24 }}>
                No topics yet — add material below and they’ll organise themselves in.
              </Text>
            )}

            {topics.length > 0 && sectionLabel('Topics')}
            {topics.map((topic) => (
              <Pressable
                key={topic.id}
                onPress={() => router.push({ pathname: '/note', params: { topicId: topic.id, courseId } })}
                style={{ paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: c.paperEdge, minHeight: 44, gap: 2 }}
              >
                <Text style={{ fontWeight: '600', fontSize: 17, color: c.ink }}>{topic.title}</Text>
                <Text style={{ fontSize: size.caption, color: c.inkTertiary }}>{topicSubtitle(topic)}</Text>
              </Pressable>
            ))}
          </ScrollView>
        )}

        <View style={{ padding: space.gutterPage, borderTopWidth: 1, borderTopColor: c.paperEdge }}>
          <Pressable
            onPress={() => router.push({ pathname: '/capture', params: { courseId } })}
            disabled={!courseId}
            style={{ minHeight: 44, justifyContent: 'center' }}
          >
            <Text style={{ color: c.confirm, textDecorationLine: 'underline', fontSize: size.bodySm }}>
              Add material to this course
            </Text>
          </Pressable>
        </View>
      </View>
    </SafeAreaView>
  );
}
