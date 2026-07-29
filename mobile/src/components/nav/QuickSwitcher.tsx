import { router } from 'expo-router';
import React, { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useTheme } from '@/theme/ThemeProvider';
import { MyCourse, fetchMyCourses } from '@/lib/courses';
import { useQuickSwitcher } from './QuickSwitcherContext';

// The global jump: from anywhere it's mounted (home + every course/topic header), one tap
// to open, one tap to land on a note or course — the ≤2-click path to any note. Built
// entirely from GET /api/courses (courses + embedded topics + last_studied), so a topic
// row routes straight to its note with the real ids.
type DirectoryItem =
  | { key: string; kind: 'course'; label: string; sub: string; courseId: string }
  | { key: string; kind: 'note'; label: string; sub: string; topicId: string; courseId: string };

const TYPE_LABEL: Record<DirectoryItem['kind'], string> = { course: 'Course', note: 'Note' };

function DirectoryRow({ item, onSelect }: { item: DirectoryItem; onSelect: (item: DirectoryItem) => void }) {
  const { c, font, size, trackingUtility } = useTheme();
  return (
    <Pressable onPress={() => onSelect(item)} style={[styles.row, { borderBottomColor: c.paperEdge }]}>
      <View style={{ flex: 1, paddingRight: 12 }}>
        <Text style={{ fontFamily: font.body, fontSize: 16, color: c.ink }}>{item.label}</Text>
        <Text style={{ fontSize: size.caption, color: c.inkTertiary }}>{item.sub}</Text>
      </View>
      <Text style={{ fontFamily: font.utility, fontSize: size.caption, letterSpacing: trackingUtility(size.caption), textTransform: 'uppercase', color: c.inkTertiary }}>
        {TYPE_LABEL[item.kind]}
      </Text>
    </Pressable>
  );
}

export function QuickSwitcher() {
  const { c, font, size, radius, trackingUtility } = useTheme();
  const { open, closeSwitcher } = useQuickSwitcher();
  const [query, setQuery] = useState('');
  const [courses, setCourses] = useState<MyCourse[]>([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  // Refetch each time the switcher opens so it reflects freshly created/joined courses.
  useEffect(() => {
    if (!open) return;
    let alive = true;
    (async () => {
      setLoading(true);
      try {
        const list = await fetchMyCourses();
        if (alive) setCourses(list);
      } catch {
        if (alive) setCourses([]);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [open]);

  // Reset to a collapsed, empty-query state on close so the next open starts clean.
  const close = () => {
    setQuery('');
    setExpanded(new Set());
    closeSwitcher();
  };

  const toggle = (courseId: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(courseId)) next.delete(courseId);
      else next.add(courseId);
      return next;
    });

  // Flatten courses + their topics into one searchable directory.
  const directory = useMemo<DirectoryItem[]>(() => {
    const items: DirectoryItem[] = [];
    for (const course of courses) {
      items.push({ key: `c-${course.id}`, kind: 'course', label: course.name, sub: course.code, courseId: course.id });
      for (const topic of course.topics) {
        items.push({ key: `t-${topic.id}`, kind: 'note', label: topic.title, sub: course.code, topicId: topic.id, courseId: course.id });
      }
    }
    return items;
  }, [courses]);

  // Recents = most-recently-studied note per course, newest first (from last_studied).
  const recents = useMemo<DirectoryItem[]>(() => {
    return courses
      .filter((course) => course.last_studied)
      .map((course) => ({ course, ls: course.last_studied! }))
      .sort((a, b) => (a.ls.studied_at < b.ls.studied_at ? 1 : -1))
      .slice(0, 5)
      .map(({ course, ls }) => ({
        key: `r-${ls.topic_id}`,
        kind: 'note' as const,
        label: ls.topic_name,
        sub: course.code,
        topicId: ls.topic_id,
        courseId: course.id,
      }));
  }, [courses]);

  const filtered = useMemo(
    () => directory.filter((r) => r.label.toLowerCase().includes(query.toLowerCase())),
    [directory, query]
  );
  const showRecents = !query && recents.length > 0;

  const select = (item: DirectoryItem) => {
    close();
    if (item.kind === 'course') {
      router.push({ pathname: '/topics', params: { courseId: item.courseId } });
    } else {
      router.push({ pathname: '/note', params: { topicId: item.topicId, courseId: item.courseId } });
    }
  };

  const openNote = (topicId: string, courseId: string) => {
    close();
    router.push({ pathname: '/note', params: { topicId, courseId } });
  };

  const sectionLabel = [styles.label, { fontFamily: font.utility, fontSize: size.caption, letterSpacing: trackingUtility(size.caption), color: c.inkTertiary }];

  return (
    <Modal visible={open} transparent animationType="fade" onRequestClose={close}>
      <View style={styles.root}>
        <Pressable style={[StyleSheet.absoluteFill, styles.scrim, { backgroundColor: c.ink }]} onPress={close} />
        <View style={[styles.panel, { backgroundColor: c.paper, borderBottomColor: c.paperEdge }]}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 14 }}>
            <TextInput
              autoFocus
              placeholder="Jump to any course, topic, or note"
              placeholderTextColor={c.inkTertiary}
              value={query}
              onChangeText={setQuery}
              style={[styles.search, { flex: 1, marginBottom: 0, borderColor: c.paperEdge, borderRadius: radius.sm, backgroundColor: c.paper, color: c.ink }]}
            />
            <Pressable onPress={close} accessibilityLabel="Close" hitSlop={8} style={{ minHeight: 44, justifyContent: 'center' }}>
              <Text style={{ color: c.confirm, fontSize: 16 }}>Cancel</Text>
            </Pressable>
          </View>
          {loading ? (
            <View style={{ paddingTop: 30, alignItems: 'center' }}>
              <ActivityIndicator color={c.ink} />
            </View>
          ) : query ? (
            // Searching: flat results across courses + topics.
            <ScrollView keyboardShouldPersistTaps="handled">
              <Text style={sectionLabel}>Results</Text>
              {filtered.map((r) => (
                <DirectoryRow key={r.key} item={r} onSelect={select} />
              ))}
              {filtered.length === 0 && (
                <Text style={{ color: c.inkTertiary, fontSize: size.bodySm, paddingVertical: 12 }}>
                  {directory.length === 0 ? 'No courses yet — create or join one first.' : `Nothing matches “${query}”`}
                </Text>
              )}
            </ScrollView>
          ) : (
            // Idle: recents + a collapsed course accordion (tap a course to reveal its topics).
            <ScrollView keyboardShouldPersistTaps="handled">
              {showRecents && (
                <>
                  <Text style={sectionLabel}>Recents</Text>
                  {recents.map((r) => (
                    <DirectoryRow key={r.key} item={r} onSelect={select} />
                  ))}
                </>
              )}
              <Text style={[sectionLabel, { marginTop: showRecents ? 20 : 0 }]}>Courses</Text>
              {courses.length === 0 ? (
                <Text style={{ color: c.inkTertiary, fontSize: size.bodySm, paddingVertical: 12 }}>
                  No courses yet — create or join one first.
                </Text>
              ) : (
                courses.map((course) => {
                  const isOpen = expanded.has(course.id);
                  return (
                    <View key={course.id}>
                      <Pressable
                        onPress={() => toggle(course.id)}
                        style={{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12, minHeight: 44, borderBottomWidth: 1, borderBottomColor: c.paperEdge }}
                      >
                        <Text style={{ color: c.inkTertiary, fontSize: 14, width: 14 }}>{isOpen ? '▾' : '▸'}</Text>
                        <View style={{ flex: 1 }}>
                          <Text style={{ fontFamily: font.body, fontSize: 16, color: c.ink }}>{course.name}</Text>
                          <Text style={{ fontSize: size.caption, color: c.inkTertiary }}>{course.code}</Text>
                        </View>
                      </Pressable>
                      {isOpen &&
                        (course.topics.length === 0 ? (
                          <Text style={{ color: c.inkTertiary, fontSize: size.bodySm, paddingVertical: 10, paddingLeft: 26 }}>
                            No topics yet
                          </Text>
                        ) : (
                          course.topics.map((topic) => (
                            <Pressable
                              key={topic.id}
                              onPress={() => openNote(topic.id, course.id)}
                              style={{ paddingVertical: 10, paddingLeft: 26, minHeight: 44, justifyContent: 'center', borderBottomWidth: 1, borderBottomColor: c.paperEdge }}
                            >
                              <Text style={{ fontFamily: font.body, fontSize: 15, color: c.ink }}>{topic.title}</Text>
                            </Pressable>
                          ))
                        ))}
                    </View>
                  );
                })
              )}
            </ScrollView>
          )}
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  scrim: { opacity: 0.3 },
  panel: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, borderBottomWidth: 1, padding: 20, paddingTop: 60 },
  search: { fontSize: 16, paddingHorizontal: 14, paddingVertical: 12, marginBottom: 14, borderWidth: 1, minHeight: 44 },
  label: { textTransform: 'uppercase', marginBottom: 8 },
  row: { paddingVertical: 12, borderBottomWidth: 1, minHeight: 44, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
});
