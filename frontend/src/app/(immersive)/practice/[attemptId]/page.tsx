'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ImmersiveLayout } from '@/components/layouts/ImmersiveLayout';
import { TestTopBar } from '@/components/layouts/TopBar';
import { MCQAnswerButton } from '@/components/ui/MCQAnswerButton';
import { TestNavButtons } from '@/components/ui/TestNavButtons';
import { Textarea } from '@/components/ui/Textarea';
import { LinearProgressBar } from '@/components/data-display/LinearProgressBar';
import { AutoSaveIndicator } from '@/components/feedback/AutoSaveIndicator';
import { TimerWidget } from '@/components/feedback/TimerWidget';
import { VoiceRecorderWidget } from '@/components/ai/VoiceRecorderWidget';
import { Modal } from '@/components/feedback/Modal';
import { Skeleton } from '@/components/feedback/Skeleton';
import { useToast } from '@/components/feedback/ToastProvider';
import { api } from '@/lib/api';

type SaveState = 'idle' | 'saving' | 'saved' | 'error';

interface Question {
  id: string;
  question_text: string;
  question_type: 'mcq' | 'short_answer';
  options?: string[];
}

const OPTIONS_LABELS = ['A', 'B', 'C', 'D', 'E'];

export default function TakeTestPage() {
  const { attemptId } = useParams<{ attemptId: string }>();
  const router = useRouter();
  const toast = useToast();

  const [questions, setQuestions]   = useState<Question[]>([]);
  const [testId, setTestId]         = useState('');
  const [current, setCurrent]       = useState(0);
  const [answers, setAnswers]       = useState<Record<string, string>>({});
  const [voiceFiles, setVoiceFiles] = useState<Record<string, File>>({});
  const [loading, setLoading]       = useState(true);
  const [saveState, setSaveState]   = useState<SaveState>('idle');
  const [submitting, setSubmitting] = useState(false);
  const [exitModal, setExitModal]   = useState(false);
  const [submitModal, setSubmitModal] = useState(false);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    api.ai.getTest(attemptId).then((r) => {
      const test = r.data;
      setTestId(test.id);
      setQuestions(test.questions ?? []);
    }).catch(() => toast.error('Failed to load test.')).finally(() => setLoading(false));
  }, [attemptId, toast]);

  const q = questions[current];
  const total = questions.length;
  const isLast = current === total - 1;

  const setAnswer = (val: string) => {
    setAnswers((prev) => ({ ...prev, [q.id]: val }));
    setSaveState('saving');
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      try {
        await api.ai.saveDraft?.(testId, [{ question_id: q.id, answer_text: val }]);
        setSaveState('saved');
      } catch {
        setSaveState('error');
      }
    }, 1500);
  };

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      const payload = questions.map((q) => ({
        question_id: q.id,
        answer_text: answers[q.id] ?? '',
        is_voice: !!voiceFiles[q.id],
      }));
      const res = await api.ai.submitFull(testId, payload, voiceFiles);
      const newAttemptId = res.data.attempt_id ?? res.data.id;
      router.replace(`/practice/${newAttemptId}/results`);
    } catch {
      toast.error('Failed to submit test. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <ImmersiveLayout
        topBar={<div className="h-[60px] glass-nav" />}
      >
        <div className="max-w-2xl mx-auto px-4 py-8">
          <Skeleton className="h-4 w-full mb-6" />
          <Skeleton className="h-6 w-3/4 mb-8" variant="text" />
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-14 mb-3" />)}
        </div>
      </ImmersiveLayout>
    );
  }

  return (
    <ImmersiveLayout
      topBar={
        <TestTopBar
          onExit={() => setExitModal(true)}
          current={current + 1}
          total={total}
          timerEl={<TimerWidget durationSeconds={3600} />}
        />
      }
      footerBar={
        <TestNavButtons
          onPrev={() => setCurrent((c) => Math.max(0, c - 1))}
          onNext={() => setCurrent((c) => Math.min(total - 1, c + 1))}
          onSubmit={() => setSubmitModal(true)}
          hasPrev={current > 0}
          hasNext={current < total - 1}
          isLast={isLast}
          saveState={saveState}
          submitting={submitting}
        />
      }
    >
      {q && (
        <div className="max-w-2xl mx-auto px-4 py-6">
          {/* Progress */}
          <LinearProgressBar value={Math.round(((current + 1) / total) * 100)} size="thin" className="mb-6" />

          {/* Question */}
          <p className="text-xs uppercase tracking-wider font-bold text-[var(--text-tertiary)] mb-3">
            Question {current + 1}
          </p>
          <h2 className="font-display font-semibold text-xl text-[var(--text-primary)] leading-snug mb-8">
            {q.question_text}
          </h2>

          {/* MCQ */}
          {q.question_type === 'mcq' && q.options && (
            <div className="flex flex-col gap-3">
              {q.options.map((opt, i) => (
                <MCQAnswerButton
                  key={i}
                  option={OPTIONS_LABELS[i]}
                  text={opt}
                  selected={answers[q.id] === opt}
                  onClick={() => setAnswer(opt)}
                />
              ))}
            </div>
          )}

          {/* Short answer / essay */}
          {q.question_type === 'short_answer' && (
            <div className="flex flex-col gap-4">
              <Textarea
                variant="essay"
                value={answers[q.id] ?? ''}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder="Type your answer here…"
                rows={8}
              />
              <VoiceRecorderWidget
                onRecordingComplete={(file) => setVoiceFiles((p) => ({ ...p, [q.id]: file }))}
                onClear={() => setVoiceFiles((p) => { const n = { ...p }; delete n[q.id]; return n; })}
              />
            </div>
          )}
        </div>
      )}

      {/* Exit confirmation */}
      <Modal
        open={exitModal}
        onClose={() => setExitModal(false)}
        title="Exit test?"
        variant="destructive"
        confirmLabel="Exit"
        onConfirm={() => router.back()}
      >
        Your progress will be lost. Are you sure you want to exit?
      </Modal>

      {/* Submit confirmation */}
      <Modal
        open={submitModal}
        onClose={() => setSubmitModal(false)}
        title="Submit test?"
        variant="default"
        confirmLabel="Submit"
        onConfirm={handleSubmit}
        loading={submitting}
      >
        You answered {Object.keys(answers).length} of {total} questions. Unanswered questions will score 0.
      </Modal>
    </ImmersiveLayout>
  );
}
