import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, View } from 'react-native';
import { isAxiosError } from 'axios';
import { router } from 'expo-router';
import { useTheme } from '@/theme/ThemeProvider';
import { Sheet } from '@/components/ui/Sheet';
import { MyCourse, fetchMyCourses } from '@/lib/courses';

// Bottom-sheet course chooser. "Add material" needs a destination course before it can
// open capture, so this fetches the user's courses and hands the chosen id back. Keeps
// the pick to one tap (sheet stays over the current screen — no page navigation).
interface CoursePickerSheetProps {
  open: boolean;
  onClose: () => void;
  onSelect: (courseId: string) => void;
  title?: string;
}

function readError(err: unknown): string {
  if (isAxiosError(err) && typeof err.response?.data?.detail === 'string') return err.response.data.detail;
  return 'Couldn’t load your courses.';
}

export function CoursePickerSheet({ open, onClose, onSelect, title = 'Add to which course?' }: CoursePickerSheetProps) {
  const { c, font, size } = useTheme();
  const [courses, setCourses] = useState<MyCourse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let alive = true;
    (async () => {
      setLoading(true);
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
  }, [open]);

  return (
    <Sheet open={open} onClose={onClose} title={title}>
      {loading ? (
        <View style={{ paddingVertical: 30, alignItems: 'center' }}>
          <ActivityIndicator color={c.ink} />
        </View>
      ) : error ? (
        <Text style={{ color: c.stateShaky, fontSize: size.bodySm, paddingVertical: 12 }}>{error}</Text>
      ) : courses.length === 0 ? (
        <View style={{ gap: 12, paddingVertical: 8 }}>
          <Text style={{ color: c.inkSecondary, fontSize: size.body }}>No courses yet.</Text>
          <Pressable
            onPress={() => {
              onClose();
              router.push('/coursecreate');
            }}
            style={{ minHeight: 44, justifyContent: 'center' }}
          >
            <Text style={{ color: c.confirm, textDecorationLine: 'underline', fontSize: size.body }}>Create a course</Text>
          </Pressable>
        </View>
      ) : (
        <ScrollView>
          {courses.map((course) => (
            <Pressable
              key={course.id}
              onPress={() => onSelect(course.id)}
              style={{ paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: c.paperEdge, minHeight: 44 }}
            >
              <Text style={{ fontFamily: font.bodySemibold, fontSize: 16, color: c.ink }}>{course.name}</Text>
              <Text style={{ fontSize: size.caption, color: c.inkTertiary }}>{course.code}</Text>
            </Pressable>
          ))}
        </ScrollView>
      )}
    </Sheet>
  );
}
