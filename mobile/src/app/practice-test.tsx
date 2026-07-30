import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, Text, TextStyle, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { router, useLocalSearchParams } from 'expo-router';
import { useTheme } from '@/theme/ThemeProvider';
import { Button } from '@/components/ui/Button';
import { Textarea } from '@/components/ui/Textarea';
import { MathText } from '@/components/retrieval/MathText';
import { CONF_LEVELS, ConfLevel, gradeColor, labelStyle, readError } from '@/components/retrieval/retrievalShared';
import { usePracticeTestSocket } from '@/lib/usePracticeTestSocket';
import {
  PtAnswerResult,
  PtQuestion,
  TestDetail,
  TestResult,
  answerQuestion,
  getTest,
  getTestResult,
} from '@/lib/practiceTest';

type Stage = 'loading' | 'error' | 'answering' | 'result';
type QPhase = 'confidence' | 'answer' | 'graded';

export default function PracticeTestRunner() {
  const theme = useTheme();
  const { c } = theme;
  const params = useLocalSearchParams<{ testId?: string }>();
  const testId = typeof params.testId === 'string' ? params.testId : undefined;

  const [stage, setStage] = useState<Stage>(testId ? 'loading' : 'error');
  const [test, setTest] = useState<TestDetail | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(testId ? null : 'No test to open.');
  const [result, setResult] = useState<TestResult | null>(null);

  const [qIndex, setQIndex] = useState(0);
  const [qPhase, setQPhase] = useState<QPhase>('confidence');
  const [confidence, setConfidence] = useState<ConfLevel | null>(null);
  const [text, setText] = useState('');
  const [graded, setGraded] = useState<PtAnswerResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [courseId, setCourseId] = useState<string | undefined>(undefined);

  // One read up front. Usually the builder navigates here already-ready; if opened mid-generation
  // (a share link), we hand off to the WS below rather than polling.
  useEffect(() => {
    if (!testId) return;
    let alive = true;
    getTest(testId)
      .then((detail) => {
        if (!alive) return;
        setCourseId(detail.course_id);
        if (detail.generation_status === 'ready') {
          setTest(detail);
          setStage('answering');
        } else if (detail.generation_status === 'failed') {
          setErrorMsg('This test failed to generate.');
          setStage('error');
        }
      })
      .catch((err) => {
        if (!alive) return;
        setErrorMsg(readError(err));
        setStage('error');
      });
    return () => {
      alive = false;
    };
  }, [testId]);

  // Still generating (share link) → wait for the worker's completion event, then load questions.
  usePracticeTestSocket(courseId, testId, stage === 'loading', {
    onComplete: () => {
      if (!testId) return;
      getTest(testId)
        .then((detail) => {
          setTest(detail);
          setStage('answering');
        })
        .catch((err) => {
          setErrorMsg(readError(err));
          setStage('error');
        });
    },
    onFailed: (reason) => {
      setErrorMsg(reason);
      setStage('error');
    },
  });

  const questions = test?.questions ?? [];
  const question: PtQuestion | undefined = questions[qIndex];

  const nextQuestion = async () => {
    if (qIndex + 1 < questions.length) {
      setQIndex((i) => i + 1);
      setQPhase('confidence');
      setConfidence(null);
      setText('');
      setGraded(null);
      return;
    }
    if (!testId) return;
    setStage('loading');
    try {
      setResult(await getTestResult(testId));
      setStage('result');
    } catch (err) {
      setErrorMsg(readError(err));
      setStage('error');
    }
  };

  const submit = async (response: unknown) => {
    if (!test || !question || submitting) return;
    setSubmitting(true);
    try {
      const res = await answerQuestion(test.id, question.id, {
        response,
        predicted_confidence: confidence?.v ?? null,
      });
      setGraded(res);
      setQPhase('graded');
    } catch (err) {
      setErrorMsg(readError(err));
      setStage('error');
    } finally {
      setSubmitting(false);
    }
  };

  const questionStyle: TextStyle = {
    fontFamily: theme.font.display,
    fontWeight: '500',
    fontSize: theme.size.display3,
    lineHeight: theme.size.display3 * theme.lineHeight.display,
    color: c.ink,
  };
  const optionStyle = {
    minHeight: 44,
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderRadius: theme.radius.md,
    borderWidth: 1,
    borderColor: c.paperEdge,
    backgroundColor: c.paper,
    justifyContent: 'center' as const,
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: c.paper }}>
      <View style={{ paddingHorizontal: 20, paddingTop: 18, paddingBottom: 10, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text style={labelStyle(theme)}>
          {test ? `${test.title} · ${Math.min(qIndex + 1, questions.length)}/${questions.length}` : 'Practice test'}
        </Text>
        <Pressable onPress={() => router.back()} style={{ minHeight: 44, minWidth: 44, alignItems: 'flex-end', justifyContent: 'center' }} accessibilityLabel="Close">
          <Text style={{ fontSize: 20, color: c.inkSecondary }}>✕</Text>
        </Pressable>
      </View>

      <ScrollView contentContainerStyle={{ paddingHorizontal: 20, paddingBottom: 28, gap: 16, flexGrow: 1, justifyContent: stage === 'answering' ? 'flex-start' : 'center' }}>
        {stage === 'loading' && <ActivityIndicator color={c.ink} />}

        {stage === 'error' && (
          <View style={{ gap: 14 }}>
            <Text style={{ fontFamily: theme.font.display, fontSize: theme.size.display3, color: c.ink }}>Can’t open this test</Text>
            <Text style={{ fontSize: theme.size.body, color: c.inkSecondary }}>{errorMsg}</Text>
            <Button label="Back" onPress={() => router.back()} />
          </View>
        )}

        {stage === 'answering' && question && (
          <>
            <MathText content={question.prompt} textStyle={questionStyle} />

            {qPhase === 'confidence' && (
              <View style={{ gap: 10 }}>
                <Text style={labelStyle(theme)}>Before you answer — how sure are you?</Text>
                {CONF_LEVELS.map((lvl) => (
                  <Pressable key={lvl.label} onPress={() => { setConfidence(lvl); setQPhase('answer'); }} style={optionStyle}>
                    <Text style={{ fontFamily: theme.font.body, fontSize: 16, color: c.ink }}>{lvl.label}</Text>
                  </Pressable>
                ))}
              </View>
            )}

            {qPhase === 'answer' && (
              <View style={{ gap: 12 }}>
                {question.payload.question_type === 'mcq' && Array.isArray(question.payload.answer_options) ? (
                  question.payload.answer_options.map((opt) => (
                    <Pressable key={opt} onPress={() => submit(opt)} disabled={submitting} style={optionStyle}>
                      <Text style={{ fontFamily: theme.font.body, fontSize: 16, color: c.ink }}>{opt}</Text>
                    </Pressable>
                  ))
                ) : (
                  <>
                    <Textarea rows={question.payload.question_type === 'essay' ? 6 : 2} value={text} onChangeText={setText} placeholder="Type your answer…" />
                    <Button label={submitting ? 'Checking…' : 'Submit'} disabled={submitting || text.trim().length === 0} onPress={() => submit(text)} />
                  </>
                )}
              </View>
            )}

            {qPhase === 'graded' && graded && (
              <QuestionFeedback result={graded} last={qIndex + 1 >= questions.length} onNext={nextQuestion} />
            )}
          </>
        )}

        {stage === 'result' && result && <ResultView result={result} onDone={() => router.back()} />}
      </ScrollView>
    </SafeAreaView>
  );
}

function QuestionFeedback({ result, last, onNext }: { result: PtAnswerResult; last: boolean; onNext: () => void }) {
  const theme = useTheme();
  const { c } = theme;
  const { outcome } = result;
  const headline = outcome.score >= 1 ? 'Correct.' : outcome.score > 0 ? `${Math.round(outcome.score * 10)} / 10` : 'Not quite.';
  return (
    <View style={{ gap: 12, marginTop: 4 }}>
      <Text style={[labelStyle(theme, gradeColor(theme, outcome.grade)), { fontSize: theme.size.body }]}>{headline}</Text>
      {outcome.feedback && <MathText content={outcome.feedback} textStyle={{ fontSize: theme.size.body, color: c.inkSecondary }} />}
      <Button label={last ? 'See results' : 'Next question'} onPress={onNext} />
    </View>
  );
}

function ResultView({ result, onDone }: { result: TestResult; onDone: () => void }) {
  const theme = useTheme();
  const { c } = theme;
  const mean = result.mean_score != null ? `${Math.round(result.mean_score * 100)}%` : '—';
  return (
    <View style={{ gap: 14 }}>
      <Text style={{ fontFamily: theme.font.display, fontSize: theme.size.display2, color: c.ink }}>
        {`${result.firmed_count} of ${result.question_count} firmed up`}
      </Text>
      <Text style={{ fontSize: theme.size.bodySm, color: c.inkSecondary }}>
        {`${result.answered_count} answered · ${mean} average · these all feed your spaced review`}
      </Text>
      <View style={{ gap: 10, marginTop: 6 }}>
        {result.concepts.map((r) => (
          <View key={r.concept_id} style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: c.paperEdge }}>
            <Text style={{ color: c.ink, fontSize: theme.size.body, flex: 1, paddingRight: 12 }}>{r.concept_text}</Text>
            <Text style={labelStyle(theme, r.grade ? gradeColor(theme, r.grade) : c.inkTertiary)}>{r.grade ?? 'skipped'}</Text>
          </View>
        ))}
      </View>
      <Button label="Done" onPress={onDone} />
    </View>
  );
}
