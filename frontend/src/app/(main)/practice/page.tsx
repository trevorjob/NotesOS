'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import { PracticeTestListRow } from '@/components/cards/PracticeTestListRow';
import { MetricCard } from '@/components/cards/MetricCard';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Skeleton } from '@/components/feedback/Skeleton';
import { Select } from '@/components/ui/Select';
import { Button } from '@/components/ui/Button';
import { apiClient } from '@/lib/api';

interface TestAttempt {
  id: string;
  test_id: string;
  created_at: string;
  score?: number | null;
  status: 'graded' | 'pending' | 'draft';
  question_count: number;
  course_code?: string;
}

interface TestStats {
  avg_score?: number;
  tests_completed?: number;
  study_streak?: number;
}

interface Course { id: string; code: string; name: string; }

function PracticeListContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const courseParam = searchParams.get('course') ?? '';

  const [attempts, setAttempts]   = useState<TestAttempt[]>([]);
  const [stats, setStats]         = useState<TestStats>({});
  const [courses, setCourses]     = useState<Course[]>([]);
  const [selectedCourse, setSelCourse] = useState(courseParam);
  const [loading, setLoading]     = useState(true);

  useEffect(() => {
    apiClient.get('/api/courses').then((r) => setCourses(r.data.courses ?? [])).catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    const params = selectedCourse ? { course_id: selectedCourse } : {};
    Promise.all([
      apiClient.get('/api/tests', { params }).catch(() => ({ data: { tests: [] } })),
      selectedCourse
        ? apiClient.get('/api/tests/stats', { params: { course_id: selectedCourse } }).catch(() => ({ data: {} }))
        : Promise.resolve({ data: {} }),
    ]).then(([testsRes, statsRes]) => {
      const tests = testsRes.data.tests ?? [];
      const allAttempts: TestAttempt[] = [];
      for (const t of tests) {
        if (t.attempts) {
          for (const a of t.attempts) {
            allAttempts.push({ id: a.id, test_id: t.id, created_at: a.created_at, score: a.score, status: a.status ?? 'pending', question_count: t.question_count ?? 0, course_code: t.course_code });
          }
        }
      }
      allAttempts.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
      setAttempts(allAttempts);
      setStats(statsRes.data ?? {});
    }).finally(() => setLoading(false));
  }, [selectedCourse]);

  return (
    <div className="px-4 md:px-8 py-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="font-display font-bold text-xl text-[var(--text-primary)]">Practice Tests</h1>
        <Button variant="primary" size="sm" onClick={() => router.push('/practice/generate')} iconLeft="add">
          New Test
        </Button>
      </div>

      {/* Stats */}
      {(stats.avg_score != null || stats.tests_completed != null) && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          <MetricCard icon="grade" value={stats.avg_score != null ? `${Math.round(stats.avg_score)}%` : '—'} label="Avg score" />
          <MetricCard icon="quiz" value={stats.tests_completed ?? 0} label="Tests done" />
          <MetricCard icon="local_fire_department" value={stats.study_streak ?? 0} label="Day streak" iconFilled />
        </div>
      )}

      {/* Filter */}
      {courses.length > 0 && (
        <Select
          label="Filter by course"
          value={selectedCourse}
          onChange={(e) => setSelCourse(e.target.value)}
          options={courses.map((c) => ({ value: c.id, label: `${c.code} — ${c.name}` }))}
          placeholder="All courses"
          containerClassName="max-w-xs mb-6"
        />
      )}

      {/* List */}
      {loading ? (
        <div className="flex flex-col gap-3">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-16" />)}
        </div>
      ) : attempts.length === 0 ? (
        <EmptyState
          icon="quiz"
          title="No practice tests yet"
          body="Generate an AI test from your course materials and practice for your exams."
          ctaLabel="Generate Test"
          onCta={() => router.push('/practice/generate')}
        />
      ) : (
        <div className="flex flex-col gap-3">
          {attempts.map((a) => (
            <PracticeTestListRow
              key={a.id}
              id={a.test_id}
              attemptId={a.id}
              date={a.created_at}
              score={a.status === 'graded' ? a.score ?? null : null}
              questionCount={a.question_count}
              status={a.status}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function PracticeTestsPage() {
  return (
    <Suspense fallback={<div className="p-8"><Skeleton className="h-8 w-48 mb-6" variant="text" /></div>}>
      <PracticeListContent />
    </Suspense>
  );
}
