import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { isAxiosError } from 'axios';
import { useTheme } from '@/theme/ThemeProvider';
import { joinCourse } from '@/lib/courses';
import {
  Classmate,
  DiscoverCourse,
  courseReason,
  fetchClassmates,
  fetchDiscoverCourses,
} from '@/lib/discovery';

function readError(err: unknown): string {
  if (isAxiosError(err) && typeof err.response?.data?.detail === 'string') {
    return err.response.data.detail;
  }
  return 'Couldn’t load discovery. Pull to try again.';
}

export default function DiscoveryScreen() {
  const { c, font, size, space, trackingUtility } = useTheme();

  const [courses, setCourses] = useState<DiscoverCourse[]>([]);
  const [classmates, setClassmates] = useState<Classmate[]>([]);
  const [joinedIds, setJoinedIds] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [discoverCourses, discoverClassmates] = await Promise.all([
          fetchDiscoverCourses(),
          fetchClassmates(),
        ]);
        if (!alive) return;
        setCourses(discoverCourses);
        setClassmates(discoverClassmates);
      } catch (err) {
        if (alive) setError(readError(err));
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const join = async (courseId: string) => {
    setError(null);
    setSubmitting(true);
    try {
      await joinCourse({ courseId });
      setJoinedIds((prev) => [...prev, courseId]);
    } catch (err) {
      setError(readError(err));
    } finally {
      setSubmitting(false);
    }
  };

  const sectionLabel = (label: string, marginTop: number) => (
    <Text
      style={{
        fontFamily: font.utility,
        fontSize: size.caption,
        letterSpacing: trackingUtility(size.caption),
        textTransform: 'uppercase',
        color: c.inkTertiary,
        marginTop,
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
          <Pressable onPress={() => router.back()} style={{ minHeight: 44, justifyContent: 'center' }}>
            <Text style={{ color: c.inkSecondary, fontSize: size.bodySm }}>← Courses</Text>
          </Pressable>
          <Text style={{ fontFamily: font.display, fontSize: size.display2, color: c.ink, marginTop: 4 }}>Discover</Text>
        </View>

        {loading ? (
          <View style={{ paddingTop: 60, alignItems: 'center', gap: 14 }}>
            <ActivityIndicator color={c.ink} />
            <Text style={{ color: c.inkSecondary, fontSize: size.body }}>Finding your people…</Text>
          </View>
        ) : (
          <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingHorizontal: space.gutterPage, paddingBottom: 20 }}>
            {error && (
              <Text style={{ color: c.stateShaky, fontSize: size.bodySm, marginTop: 14 }}>{error}</Text>
            )}

            {sectionLabel('Courses to join', 14)}
            {courses.length === 0 ? (
              <Text style={{ color: c.inkTertiary, fontSize: size.bodySm, paddingVertical: 12 }}>
                Nothing yet — join or create a course and this fills up as your school gets active.
              </Text>
            ) : (
              courses.map((course) => {
                const joined = joinedIds.includes(course.course_id);
                return (
                  <View
                    key={course.course_id}
                    style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: c.paperEdge, minHeight: 44 }}
                  >
                    <View style={{ flex: 1, paddingRight: 12 }}>
                      <Text style={{ fontWeight: '600', color: c.ink }}>{course.name}</Text>
                      <Text style={{ fontSize: size.caption, color: c.inkTertiary }}>
                        {course.code} · {courseReason(course)}
                      </Text>
                    </View>
                    {joined ? (
                      <Text style={{ color: c.confirm, fontSize: size.bodySm }}>Joined ✓</Text>
                    ) : (
                      <Pressable onPress={() => join(course.course_id)} disabled={submitting} style={{ minHeight: 44, justifyContent: 'center' }}>
                        <Text style={{ color: c.confirm, textDecorationLine: 'underline', fontSize: size.bodySm }}>Join</Text>
                      </Pressable>
                    )}
                  </View>
                );
              })
            )}

            {sectionLabel('Classmates', 20)}
            {classmates.length === 0 ? (
              <Text style={{ color: c.inkTertiary, fontSize: size.bodySm, paddingVertical: 12 }}>
                Join a course to see who you study with.
              </Text>
            ) : (
              classmates.map((classmate) => (
                <View
                  key={classmate.id}
                  style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: c.paperEdge, minHeight: 44 }}
                >
                  <Text style={{ color: c.ink }}>{classmate.full_name ?? 'A classmate'}</Text>
                  <Text style={{ fontSize: size.caption, color: c.inkTertiary }}>
                    {classmate.shared_courses} shared course{classmate.shared_courses === 1 ? '' : 's'}
                  </Text>
                </View>
              ))
            )}
          </ScrollView>
        )}
      </View>
    </SafeAreaView>
  );
}
