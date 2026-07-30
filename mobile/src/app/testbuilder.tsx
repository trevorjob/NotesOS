import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleProp, Text, TextStyle, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router, useLocalSearchParams } from 'expo-router';
import { useTheme } from '@/theme/ThemeProvider';
import { Button } from '@/components/ui/Button';
import { Chip } from '@/components/ui/Chip';
import { IconButton } from '@/components/ui/IconButton';
import { Textarea } from '@/components/ui/Textarea';
import { readError } from '@/components/retrieval/retrievalShared';
import { CourseTopic, fetchCourseTopics } from '@/lib/topics';
import { usePracticeTestSocket } from '@/lib/usePracticeTestSocket';
import {
  AuthoredMode,
  PtQuestionType,
  TestSummary,
  createTest,
  getTest,
  listTests,
} from '@/lib/practiceTest';

type Stage = 'build' | 'generating' | 'ready' | 'error';

const COUNTS = [5, 10, 20];
const MODES: { id: AuthoredMode; label: string }[] = [
  { id: 'quiz', label: 'Quiz' },
  { id: 'pretest', label: 'Pretest' },
];
const TYPES: { id: PtQuestionType; label: string }[] = [
  { id: 'mcq', label: 'Multiple choice' },
  { id: 'short_answer', label: 'Short answer' },
  { id: 'essay', label: 'Essay' },
];

function Label({ children }: { children: string }) {
  const { c, font, size, trackingUtility } = useTheme();
  return (
    <Text style={{ fontFamily: font.utility, fontSize: size.utility, letterSpacing: trackingUtility(size.utility), textTransform: 'uppercase', color: c.inkSecondary }}>
      {children}
    </Text>
  );
}

export default function TestBuilder() {
  const { c, font, size, space, radius } = useTheme();
  const params = useLocalSearchParams<{ topicId?: string; courseId?: string }>();
  const courseId = typeof params.courseId === 'string' ? params.courseId : undefined;
  const topicId = typeof params.topicId === 'string' ? params.topicId : undefined;

  const [topics, setTopics] = useState<CourseTopic[]>([]);
  const [shared, setShared] = useState<TestSummary[]>([]);

  const [stage, setStage] = useState<Stage>('build');
  const [title, setTitle] = useState('');
  const [selected, setSelected] = useState<string[]>(topicId ? [topicId] : []);
  const [count, setCount] = useState(10);
  const [mode, setMode] = useState<AuthoredMode>('quiz');
  const [qType, setQType] = useState<PtQuestionType>('mcq');

  const [test, setTest] = useState<TestSummary | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!courseId) return;
    let alive = true;
    fetchCourseTopics(courseId)
      .then((detail) => {
        if (!alive) return;
        setTopics(detail.topics);
        setTitle((t) => t || `${detail.course.code} practice`);
      })
      .catch(() => {});
    listTests(courseId)
      .then((rows) => alive && setShared(rows))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, [courseId]);

  // Realtime generation: the worker pushes per-question progress + completion over the course
  // WS room, so we subscribe instead of polling. The one-shot reconcile on connect closes the
  // race where the test settled before the socket opened (not a loop — a single catch-up read).
  usePracticeTestSocket(courseId, test?.id, stage === 'generating', {
    onOpen: () => {
      const id = test?.id;
      if (!id) return;
      getTest(id)
        .then((detail) => {
          setTest(detail);
          if (detail.generation_status === 'ready') setStage('ready');
          else if (detail.generation_status === 'failed') {
            setErrorMsg('Generation failed — try fewer questions or another topic.');
            setStage('error');
          }
        })
        .catch(() => {});
    },
    onProgress: (done, total) => setTest((t) => (t ? { ...t, questions_done: done, question_count: total } : t)),
    onComplete: (total) => {
      setTest((t) => (t ? { ...t, questions_done: total, question_count: total, generation_status: 'ready' } : t));
      setStage('ready');
    },
    onFailed: (reason) => {
      setErrorMsg(reason);
      setStage('error');
    },
  });

  const toggle = (id: string) => setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));

  const generate = async () => {
    if (!courseId) return;
    setErrorMsg(null);
    setStage('generating');
    try {
      const summary = await createTest({
        course_id: courseId,
        title: title.trim(),
        mode,
        question_type: qType,
        question_count: count,
        topic_ids: selected,
      });
      setTest(summary);
    } catch (err) {
      setErrorMsg(readError(err));
      setStage('error');
    }
  };

  const titleStyle: StyleProp<TextStyle> = { fontFamily: font.display, fontSize: size.display3, color: c.ink };
  const done = test?.questions_done ?? 0;
  const total = test?.question_count ?? count;
  const topicsLabel = `Topics ${selected.length > 0 ? `· ${selected.length} picked` : '· whole course'}`;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
      <View style={{ paddingHorizontal: space.gutterPage, paddingTop: 18, paddingBottom: 10, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text style={titleStyle}>Build a practice test</Text>
        <IconButton icon={<Text style={{ fontSize: 20, color: c.inkSecondary }}>✕</Text>} label="Close" onPress={() => router.back()} />
      </View>

      <ScrollView contentContainerStyle={{ paddingHorizontal: space.gutterPage, paddingBottom: 28 }}>
        {!courseId ? (
          <Text style={{ marginTop: 40, fontSize: size.body, color: c.inkSecondary }}>
            Open a course or note first — a practice test is scoped to a course.
          </Text>
        ) : stage === 'build' ? (
          <View style={{ gap: 22 }}>
            <View>
              <Label>Title</Label>
              <View style={{ marginTop: 8 }}>
                <Textarea rows={1} value={title} onChangeText={setTitle} placeholder="Name this test…" />
              </View>
            </View>

            <View>
              <Label>{topicsLabel}</Label>
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
                {topics.map((t) => (
                  <Chip key={t.id} label={t.title} selected={selected.includes(t.id)} onPress={() => toggle(t.id)} />
                ))}
              </View>
              {topics.length === 0 && <Text style={{ marginTop: 8, fontSize: size.bodySm, color: c.inkTertiary }}>Loading topics…</Text>}
            </View>

            <View>
              <Label>Questions</Label>
              <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
                {COUNTS.map((n) => (
                  <Chip key={n} label={String(n)} selected={count === n} onPress={() => setCount(n)} />
                ))}
              </View>
            </View>

            <View>
              <Label>Style</Label>
              <View style={{ flexDirection: 'row', gap: 8, marginTop: 8 }}>
                {MODES.map((m) => (
                  <Chip key={m.id} label={m.label} selected={mode === m.id} onPress={() => setMode(m.id)} />
                ))}
              </View>
            </View>

            <View>
              <Label>Question type</Label>
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
                {TYPES.map((t) => (
                  <Chip key={t.id} label={t.label} selected={qType === t.id} onPress={() => setQType(t.id)} />
                ))}
              </View>
            </View>

            <Button label="Generate" disabled={title.trim().length === 0} onPress={generate} />

            {shared.length > 0 && (
              <View style={{ borderTopWidth: 1, borderTopColor: c.paperEdge, marginTop: 4, paddingTop: 16, gap: 8 }}>
                <Label>Shared in this course</Label>
                {shared.map((t) => (
                  <Pressable
                    key={t.id}
                    onPress={() => router.push({ pathname: '/practice-test', params: { testId: t.id } })}
                    style={{ minHeight: 44, justifyContent: 'center' }}
                  >
                    <Text style={{ fontSize: size.body, color: c.confirm }}>{t.title}</Text>
                    <Text style={{ fontSize: size.caption, color: c.inkTertiary }}>
                      {`${t.question_count} ${t.mode} · ${t.generation_status === 'ready' ? 'ready' : t.generation_status}`}
                    </Text>
                  </Pressable>
                ))}
              </View>
            )}
          </View>
        ) : stage === 'generating' ? (
          <View style={{ paddingTop: 60, alignItems: 'center', gap: 16 }}>
            <ActivityIndicator color={c.ink} />
            <Text style={titleStyle}>Writing your questions</Text>
            <Label>{`${done} of ${total}`}</Label>
            <View style={{ width: '100%', height: 4, backgroundColor: c.paperEdge, borderRadius: radius.pill, overflow: 'hidden' }}>
              <View style={{ width: `${total > 0 ? (done / total) * 100 : 0}%`, height: '100%', backgroundColor: c.ink }} />
            </View>
          </View>
        ) : stage === 'ready' && test ? (
          <View style={{ paddingTop: 40, gap: 14 }}>
            <Text style={titleStyle}>{`${test.question_count}-question test ready`}</Text>
            <Text style={{ color: c.inkSecondary, fontSize: size.bodySm }}>{`${test.title} · ${test.mode} · ${TYPES.find((t) => t.id === test.question_type)?.label}`}</Text>
            <Button label="Take it now" onPress={() => router.replace({ pathname: '/practice-test', params: { testId: test.id } })} />
            <Button label="Back" variant="text" onPress={() => router.back()} />
          </View>
        ) : (
          <View style={{ paddingTop: 40, gap: 14 }}>
            <Text style={titleStyle}>Couldn’t build that</Text>
            <Text style={{ color: c.inkSecondary, fontSize: size.body }}>{errorMsg}</Text>
            <Button label="Try again" onPress={() => setStage('build')} />
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
