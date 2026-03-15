'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { CircularScoreDisplay } from '@/components/data-display/CircularScoreDisplay';
import { TestResultQuestionCard } from '@/components/cards/TestResultQuestionCard';
import { TestResultsNextStepBlock } from '@/components/ai/TestResultsNextStepBlock';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Skeleton } from '@/components/feedback/Skeleton';
import { StatusBadge } from '@/components/feedback/StatusBadge';
import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { api } from '@/lib/api';
import { connectWebSocket } from '@/lib/websocket';

interface GradedAnswer {
  question_text: string;
  your_answer: string;
  score: number;
  feedback: string;
  encouragement?: string;
  status: 'CORRECT' | 'PARTIAL' | 'NEEDS_REVIEW';
  key_points_covered: string[];
  key_points_missed: string[];
}

interface TestResults {
  attempt_id: string;
  course_id: string;
  overall_score: number;
  graded_answers: GradedAnswer[];
  recommendations?: Array<{ topic_id: string; topic_title: string; reason: string }>;
  is_graded: boolean;
}

export default function TestResultsPage() {
  const { attemptId } = useParams<{ attemptId: string }>();
  const router = useRouter();

  const [results, setResults] = useState<TestResults | null>(null);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const wsRef = useRef<ReturnType<typeof connectWebSocket> | null>(null);

  useEffect(() => {
    api.ai.getTestResults(attemptId)
      .then((r) => {
        const data = r.data;
        if (!data.is_graded) {
          setPending(true);
          setResults(data);
        } else {
          setResults(data);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [attemptId]);

  // WebSocket listener for live grading updates
  useEffect(() => {
    if (!results?.course_id || !pending) return;

    const client = connectWebSocket(results.course_id, {
      onMessage: (msg: any) => {
        if (msg.type === 'grading_complete' && msg.attempt_id === attemptId) {
          api.ai.getTestResults(attemptId).then((r) => {
            setResults(r.data);
            setPending(false);
          });
        }
      },
      onOpen: () => {},
      onClose: () => {},
      onError: () => {},
    });
    wsRef.current = client;
    return () => { client.disconnect(); wsRef.current = null; };
  }, [results?.course_id, pending, attemptId]);

  if (loading) {
    return (
      <div className="px-4 md:px-8 py-6 max-w-3xl mx-auto">
        <Skeleton className="h-7 w-40 mb-6" variant="text" />
        <div className="flex justify-center mb-8">
          <Skeleton className="w-[120px] h-[120px]" variant="circle" />
        </div>
        {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-16 mb-3" />)}
      </div>
    );
  }

  if (!results) {
    return <EmptyState icon="error_outline" title="Results not found" body="We couldn't find results for this attempt." ctaLabel="Go back" onCta={() => router.back()} />;
  }

  if (pending) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] px-6 text-center">
        <div className="w-20 h-20 rounded-3xl bg-[var(--info-bg)] flex items-center justify-center mb-6">
          <Icon name="pending" size="xl" className="text-[var(--color-info)]" />
        </div>
        <h1 className="font-display font-bold text-2xl text-[var(--text-primary)] mb-3">
          Grading in progress
        </h1>
        <p className="text-sm text-[var(--text-secondary)] max-w-[300px] mb-6">
          AI is analysing your answers. This usually takes under a minute. Stay on this page for live updates.
        </p>
        <StatusBadge variant="info" label="Grading" pulse />
      </div>
    );
  }

  const score = Math.round(results.overall_score * 10);

  return (
    <div className="px-4 md:px-8 py-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <button
          onClick={() => router.push('/practice')}
          className="flex items-center gap-1.5 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
        >
          <Icon name="arrow_back" size="xs" /> Practice
        </button>
        <Button variant="secondary" size="sm" onClick={() => router.push('/practice/generate')}>
          New Test
        </Button>
      </div>

      {/* Score display */}
      <div className="flex flex-col items-center mb-8">
        <CircularScoreDisplay score={score} size="lg" className="mb-3" />
        <h1 className="font-display font-bold text-xl text-[var(--text-primary)]">
          {score >= 85 ? 'Excellent work!' : score >= 60 ? 'Good effort!' : 'Keep practicing!'}
        </h1>
        <p className="text-sm text-[var(--text-secondary)] mt-1">
          {results.graded_answers.length} questions graded
        </p>
      </div>

      {/* Next steps */}
      {results.recommendations && results.recommendations.length > 0 && (
        <section className="mb-8">
          <h2 className="text-xs uppercase tracking-widest font-bold text-[var(--text-tertiary)] mb-3">
            Recommended Next Steps
          </h2>
          <div className="flex flex-col gap-3">
            {results.recommendations.slice(0, 2).map((rec) => (
              <TestResultsNextStepBlock
                key={rec.topic_id}
                topicTitle={rec.topic_title}
                topicId={rec.topic_id}
                courseId={results.course_id}
                action={rec.reason}
              />
            ))}
          </div>
        </section>
      )}

      {/* Question cards */}
      <section>
        <h2 className="text-xs uppercase tracking-widest font-bold text-[var(--text-tertiary)] mb-3">
          Question Breakdown
        </h2>
        <div className="flex flex-col gap-3">
          {results.graded_answers.map((a, i) => (
            <TestResultQuestionCard
              key={i}
              questionNumber={i + 1}
              questionText={a.question_text}
              yourAnswer={a.your_answer}
              feedback={a.feedback}
              score={a.score}
              status={a.status}
              keyPointsCovered={a.key_points_covered}
              keyPointsMissed={a.key_points_missed}
              encouragement={a.encouragement}
            />
          ))}
        </div>
      </section>
    </div>
  );
}
