'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useTestsStore } from '@/stores/tests';
import { useAuthStore } from '@/stores/auth';
import type { TestResults, TestGenerationStatus } from '@/stores/tests';
import { QuizQuestion } from '@/components/quiz/QuizQuestion';
import { QuizResults } from '@/components/quiz/QuizResults';
import { Spinner } from '@/components/ui/Spinner';
import { Button } from '@/components/ui/Button';

type Phase = 'loading' | 'generating' | 'questions' | 'submitting' | 'grading' | 'results' | 'error';

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
  generation_status: TestGenerationStatus;
  batches_done: number;
  batches_total: number | null;
  failure_reason?: string | null;
}

export default function TestPage() {
  const params = useParams<{ testId: string }>();
  const { testId } = params;
  const router = useRouter();

  const [phase, setPhase] = useState<Phase>('loading');
  const [meta, setMeta] = useState<TestMeta | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, { answer_text: string; is_voice?: boolean }>>({});
  const [voiceFiles, setVoiceFiles] = useState<Record<string, File>>({});
  const [result, setResult] = useState<TestResults | null>(null);
  const [errorMsg, setErrorMsg] = useState('');
  const gradingCleanupRef = useRef<(() => void) | null>(null);
  const generationCleanupRef = useRef<(() => void) | null>(null);
  const loadingRef = useRef(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    loadTest();
    return () => {
      gradingCleanupRef.current?.();
      generationCleanupRef.current?.();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [testId]);

  // Sync streamed questions from the store into local state while generating
  useEffect(() => {
    if (phase !== 'generating') return;
    const unsub = useTestsStore.subscribe((state) => {
      const test = state.currentTest;
      if (!test || test.id !== testId) return;

      // Update meta progress
      setMeta((prev) => prev ? {
        ...prev,
        generation_status: test.generation_status,
        batches_done: test.batches_done,
        batches_total: test.batches_total,
        failure_reason: test.failure_reason,
      } : prev);

      // Sync questions that have real IDs (streamed ones have `id: streamed-N`)
      setQuestions(test.questions as Question[]);

      if (test.generation_status === 'ready') {
        // Reload from API to get proper DB-assigned question IDs before allowing submission
        useTestsStore.getState().getTest(testId).then((fresh) => {
          setQuestions(fresh.questions as Question[]);
          setMeta((prev) => prev ? { ...prev, generation_status: 'ready' } : prev);
          setPhase('questions');
        });
      }

      if (test.generation_status === 'failed') {
        if ((test.questions?.length ?? 0) > 0) {
          // Partial questions available — let user continue or retry
          setPhase('generating'); // stay on generating screen with failure UI
        } else {
          setErrorMsg(test.failure_reason ?? 'Test generation failed. Please try again.');
          setPhase('error');
        }
      }
    });
    return unsub;
  }, [phase, testId]);

  async function loadTest() {
    if (loadingRef.current) return;
    loadingRef.current = true;
    setPhase('loading');

    try {
      // Check if we're already mid-generation from the store (navigated here from generate-test)
      const storeTest = useTestsStore.getState().currentTest;
      const isFromStore = storeTest?.id === testId && storeTest.generation_status !== 'ready';

      if (isFromStore && storeTest) {
        // Already have the test in store — subscribe to generation and show live progress
        const userId = getUserIdFromToken();
        if (userId) {
          const cleanup = useTestsStore.getState().subscribeToGeneration(testId, userId);
          generationCleanupRef.current = cleanup;
        }
        setMeta({
          id: storeTest.id,
          title: storeTest.title,
          course_id: '',
          question_count: storeTest.question_count,
          generation_status: storeTest.generation_status,
          batches_done: storeTest.batches_done,
          batches_total: storeTest.batches_total,
        });
        setQuestions(storeTest.questions as Question[]);
        setPhase('generating');
      } else {
        // Fresh load (e.g. direct URL, refresh) — hydrate from API
        const fresh = await useTestsStore.getState().hydrateTest(testId);
        setMeta({
          id: fresh.id,
          title: fresh.title,
          course_id: '',
          question_count: fresh.question_count,
          generation_status: fresh.generation_status,
          batches_done: fresh.batches_done,
          batches_total: fresh.batches_total,
          failure_reason: fresh.failure_reason,
        });
        setQuestions(fresh.questions as Question[]);

        if (fresh.generation_status === 'ready') {
          setPhase('questions');
        } else if (fresh.generation_status === 'failed') {
          if (fresh.questions.length > 0) {
            setPhase('generating'); // show partial + retry
          } else {
            setErrorMsg(fresh.failure_reason ?? 'Generation failed.');
            setPhase('error');
          }
        } else {
          // Still generating — subscribe and show progress
          const userId = getUserIdFromToken();
          if (userId) {
            const cleanup = useTestsStore.getState().subscribeToGeneration(testId, userId);
            generationCleanupRef.current = cleanup;
          }
          setPhase('generating');
        }
      }
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setErrorMsg(detail || 'Could not load test. Please try again.');
      setPhase('error');
    } finally {
      loadingRef.current = false;
    }
  }

  function getUserIdFromToken(): string | null {
    return useAuthStore.getState().user?.id ?? null;
  }

  async function submitAll(finalAnswers: typeof answers, finalVoiceFiles: typeof voiceFiles) {
    setPhase('submitting');
    const answersArray = questions.map((q) => ({
      question_id: q.id,
      answer_text: finalAnswers[q.id]?.answer_text ?? '',
      is_voice: finalAnswers[q.id]?.is_voice,
    }));
    try {
      const attemptId = await useTestsStore.getState().submitFull(testId, answersArray, finalVoiceFiles);
      setPhase('grading');

      const cleanup = useTestsStore.getState().listenForGrading(attemptId, meta?.course_id ?? '', (results) => {
        setResult(results);
        setPhase('results');
      });
      gradingCleanupRef.current = cleanup;
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : 'Submission failed. Please try again.');
      setPhase('error');
    }
  }

  function handleSubmitAnswer(questionId: string, answerText: string, isVoice?: boolean, voiceFile?: File) {
    const newAnswers = { ...answers, [questionId]: { answer_text: answerText, is_voice: isVoice } };
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
    const questionId = questions[questionIndex].id;
    const newAnswers = { ...answers, [questionId]: { answer_text: '' } };
    setAnswers(newAnswers);
    if (questionIndex + 1 >= questions.length) {
      submitAll(newAnswers, voiceFiles);
    } else {
      setQuestionIndex((i) => i + 1);
    }
  }

  function handlePrevious() {
    if (questionIndex > 0) setQuestionIndex((i) => i - 1);
  }

  function shareTest() {
    navigator.clipboard.writeText(window.location.href);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const title = meta?.title ?? 'Practice Test';
  const progress = questions.length > 0 ? Math.round((questionIndex / questions.length) * 100) : 0;
  const isGenerating = phase === 'generating';
  const generationFailed = isGenerating && meta?.generation_status === 'failed';
  const readyCount = questions.length;
  const totalCount = meta?.question_count ?? 0;
  const isEssayTest = questions.length > 0 && questions[0].question_type?.toLowerCase() === 'essay';

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
        <div className="flex items-center gap-3 min-w-[64px] justify-end">
          {phase === 'questions' && questions.length > 0 && !isEssayTest && (
            <span className="text-xs text-[#6b6762]">{questionIndex + 1} / {questions.length}</span>
          )}
          {phase !== 'loading' && meta && (
            <button
              onClick={shareTest}
              className="text-xs text-[#9e9a94] hover:text-[#1a1917] transition-colors px-2 py-1 rounded-lg hover:bg-[#f0eeea]"
            >
              {copied ? 'Copied!' : 'Share'}
            </button>
          )}
        </div>
      </div>

      {/* Progress bar — only for multi-question tests */}
      {phase === 'questions' && !isEssayTest && (
        <div className="h-1 bg-[#e8e5e0]">
          <div className="h-1 bg-[#1a1917] transition-all duration-300" style={{ width: `${progress}%` }} />
        </div>
      )}

      <div className={`${isEssayTest ? 'max-w-3xl' : 'max-w-2xl'} mx-auto px-4 py-8`}>

        {phase === 'loading' && (
          <div className="flex flex-col items-center gap-3 py-16">
            <Spinner size="lg" />
            <p className="text-sm text-[#6b6762]">Loading test…</p>
          </div>
        )}

        {/* ── Generating phase — progressive reveal ── */}
        {phase === 'generating' && (
          <div className="space-y-4">
            {/* Status banner */}
            <div className="bg-white rounded-2xl border border-[#dedad4] p-5">
              {generationFailed ? (
                <div className="space-y-3">
                  <p className="text-sm font-medium text-[#1a1917]">
                    Generation stopped after {readyCount} of {totalCount} questions.
                  </p>
                  {readyCount > 0 && (
                    <p className="text-sm text-[#6b6762]">
                      You can continue with the {readyCount} question{readyCount !== 1 ? 's' : ''} that are ready, or go back and try again.
                    </p>
                  )}
                  <div className="flex gap-2 pt-1">
                    {readyCount > 0 && (
                      <Button size="sm" onClick={() => setPhase('questions')}>
                        Continue with {readyCount} questions
                      </Button>
                    )}
                    <Button size="sm" variant="ghost" onClick={() => router.push('/generate-test')}>
                      Try again
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="flex items-center gap-3">
                  <Spinner size="sm" />
                  <div>
                    <p className="text-sm font-medium text-[#1a1917]">
                      Writing questions… {readyCount > 0 ? `${readyCount} of ${totalCount} ready` : 'starting'}
                    </p>
                    <p className="text-xs text-[#9e9a94] mt-0.5">
                      Questions will appear below as they are generated. You can begin once all are ready.
                    </p>
                  </div>
                </div>
              )}

              {/* Progress bar */}
              {!generationFailed && totalCount > 0 && (
                <div className="mt-3 h-1.5 bg-[#e8e5e0] rounded-full overflow-hidden">
                  <div
                    className="h-1.5 bg-[#d97706] rounded-full transition-all duration-500"
                    style={{ width: `${Math.round((readyCount / totalCount) * 100)}%` }}
                  />
                </div>
              )}
            </div>

            {/* Preview questions — read-only */}
            {questions.length > 0 && (
              <div className="space-y-3">
                {questions.map((q, i) => (
                  <div
                    key={q.id}
                    className="bg-white rounded-xl border border-[#dedad4] p-4 opacity-70"
                  >
                    <p className="text-xs text-[#9e9a94] mb-1">Question {i + 1}</p>
                    <p className="text-sm text-[#1a1917]">{q.question_text}</p>
                    {q.answer_options && q.answer_options.length > 0 && (
                      <ul className="mt-2 space-y-1">
                        {q.answer_options.map((opt, j) => (
                          <li key={j} className="text-xs text-[#6b6762] flex items-center gap-2">
                            <span className="h-1.5 w-1.5 rounded-full bg-[#dedad4] flex-shrink-0" />
                            {opt}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            )}
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
            <p className="text-xs text-[#6b6762]">{"You'll be notified when grading is complete. This may take a moment."}</p>
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
          <div className={`bg-white rounded-2xl border border-[#dedad4] ${isEssayTest ? 'p-6 md:p-10' : 'p-6 md:p-8'}`}>
            {isEssayTest && (
              <p className="text-xs text-[#9e9a94] mb-5">
                Take your time — this is one question. Write in paragraphs, argue your point, use examples from your notes.
              </p>
            )}
            <QuizQuestion
              question={questions[questionIndex]}
              index={questionIndex}
              total={questions.length}
              onSubmit={handleSubmitAnswer}
              onSkip={handleSkip}
              onPrevious={questionIndex > 0 ? handlePrevious : undefined}
              defaultAnswer={answers[questions[questionIndex].id]?.answer_text}
              defaultIsVoice={answers[questions[questionIndex].id]?.is_voice}
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
                setAnswers({});
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
