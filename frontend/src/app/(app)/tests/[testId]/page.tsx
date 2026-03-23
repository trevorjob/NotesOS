'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { api } from '@/lib/api';
import { useTestsStore } from '@/stores/tests';
import type { TestResults } from '@/stores/tests';
import { QuizQuestion } from '@/components/quiz/QuizQuestion';
import { QuizResults } from '@/components/quiz/QuizResults';
import { Spinner } from '@/components/ui/Spinner';
import { Button } from '@/components/ui/Button';

type Phase = 'loading' | 'questions' | 'submitting' | 'grading' | 'results' | 'error';

interface Question {
  id: string;
  question_text: string;
  question_type: string;
  answer_options?: string[] | null;
  options?: string[] | null;
}

interface TestMeta {
  id: string;
  title?: string;
  course_id: string;
  question_count: number;
}

export default function TestPage() {
  const params = useParams<{ testId: string }>();
  const { testId } = params;
  const router = useRouter();

  const [phase, setPhase] = useState<Phase>('loading');
  const [meta, setMeta] = useState<TestMeta | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState<Array<{ question_id: string; answer_text: string; is_voice?: boolean }>>([]);
  const [voiceFiles, setVoiceFiles] = useState<Record<string, File>>({});
  const [result, setResult] = useState<TestResults | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const gradingCleanupRef = useRef<(() => void) | null>(null);
  const loadingRef = useRef(false);

  useEffect(() => {
    loadTest();
    return () => { gradingCleanupRef.current?.(); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [testId]);

  async function loadTest() {
    if (loadingRef.current) return;
    loadingRef.current = true;
    setPhase('loading');
    try {
      const res = await api.ai.getTest(testId);
      const test = res.data?.test ?? res.data;
      setMeta({ id: test.id, title: test.title, course_id: test.course_id, question_count: test.question_count });
      setQuestions(test.questions ?? []);
      setQuestionIndex(0);
      setAnswers([]);
      setVoiceFiles({});
      setPhase('questions');
    } catch (e: any) {
      setErrorMsg(e.response?.data?.detail || 'Could not load test. Please try again.');
      setPhase('error');
    } finally {
      loadingRef.current = false;
    }
  }

  async function submitAll(finalAnswers: typeof answers, finalVoiceFiles: typeof voiceFiles) {
    setPhase('submitting');
    try {
      const attemptId = await useTestsStore.getState().submitFull(testId, finalAnswers, finalVoiceFiles);
      setPhase('grading');

      const cleanup = useTestsStore.getState().listenForGrading(attemptId, meta?.course_id ?? '', (results) => {
        setResult(results);
        setPhase('results');
      });
      gradingCleanupRef.current = cleanup;
    } catch (e: any) {
      setErrorMsg(e.message || 'Submission failed. Please try again.');
      setPhase('error');
    }
  }

  function handleSubmitAnswer(questionId: string, answerText: string, isVoice?: boolean, voiceFile?: File) {
    const newAnswers = [...answers, { question_id: questionId, answer_text: answerText, is_voice: isVoice }];
    const newVoiceFiles = voiceFile ? { ...voiceFiles, [questionId]: voiceFile } : voiceFiles;
    setAnswers(newAnswers);
    setVoiceFiles(newVoiceFiles);

    if (questionIndex + 1 >= questions.length) {
      submitAll(newAnswers, newVoiceFiles);
    } else {
      setQuestionIndex((i) => i + 1);
    }
  }

  function handleSkip() {
    const skipped = { question_id: questions[questionIndex].id, answer_text: '' };
    const newAnswers = [...answers, skipped];
    setAnswers(newAnswers);

    if (questionIndex + 1 >= questions.length) {
      submitAll(newAnswers, voiceFiles);
    } else {
      setQuestionIndex((i) => i + 1);
    }
  }

  const title = meta?.title ?? 'Practice Test';
  const progress = questions.length > 0 ? Math.round(((questionIndex) / questions.length) * 100) : 0;

  return (
    <div className="min-h-full bg-[#f0eeea]">
      {/* Top bar */}
      <div className="sticky top-0 bg-white border-b border-[#dedad4] px-4 h-12 flex items-center justify-between z-10">
        <Link href="/generate-test" className="text-sm text-[#6b6762] hover:text-[#1a1917] flex items-center gap-1.5 transition-colors">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M9 2L4 7l5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          Generate Test
        </Link>
        <span className="text-sm font-medium text-[#1a1917] truncate max-w-[40%]">{title}</span>
        {phase === 'questions' && questions.length > 0 && (
          <span className="text-xs text-[#6b6762]">{questionIndex + 1} / {questions.length}</span>
        )}
        {phase !== 'questions' && <div className="w-16" />}
      </div>

      {/* Progress bar */}
      {phase === 'questions' && (
        <div className="h-1 bg-[#e8e5e0]">
          <div
            className="h-1 bg-[#1a1917] transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}

      <div className="max-w-2xl mx-auto px-4 py-8">

        {phase === 'loading' && (
          <div className="flex flex-col items-center gap-3 py-16">
            <Spinner size="lg" />
            <p className="text-sm text-[#6b6762]">Loading test…</p>
          </div>
        )}

        {phase === 'submitting' && (
          <div className="flex flex-col items-center gap-3 py-16">
            <Spinner size="lg" />
            <p className="text-sm text-[#6b6762]">Submitting answers…</p>
          </div>
        )}

        {phase === 'grading' && (
          <div className="bg-white rounded-2xl border border-[#dedad4] p-8 text-center space-y-3">
            <Spinner size="lg" />
            <p className="text-sm font-medium text-[#1a1917]">Grading in progress…</p>
            <p className="text-xs text-[#6b6762]">You'll be notified when grading is complete. This may take a moment.</p>
          </div>
        )}

        {phase === 'error' && (
          <div className="bg-white rounded-2xl border border-[#dedad4] p-8 text-center space-y-4">
            <p className="text-[#dc2626] text-sm">{errorMsg}</p>
            <div className="flex justify-center gap-3">
              <Button variant="ghost" onClick={() => router.push('/generate-test')}>Back</Button>
              <Button onClick={loadTest}>Try again</Button>
            </div>
          </div>
        )}

        {phase === 'questions' && questions.length > 0 && (
          <div className="bg-white rounded-2xl border border-[#dedad4] p-6 md:p-8">
            <QuizQuestion
              question={questions[questionIndex]}
              index={questionIndex}
              total={questions.length}
              onSubmit={handleSubmitAnswer}
              onSkip={handleSkip}
            />
          </div>
        )}

        {phase === 'results' && result && (
          <div className="bg-white rounded-2xl border border-[#dedad4] p-6 md:p-8">
            <QuizResults
              score={(result.total_score / result.max_score) * 100}
              questionResults={result.answers.map((a) => ({
                question_id: a.question_id,
                question_text: a.question_text,
                user_answer: a.user_answer,
                score: a.score / 10,
                feedback: a.feedback,
                encouragement: a.encouragement,
                key_points_missed: a.key_points_missed,
              }))}
              onBack={() => router.push('/generate-test')}
              onRetry={() => {
                setQuestionIndex(0);
                setAnswers([]);
                setVoiceFiles({});
                setResult(null);
                loadTest();
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
