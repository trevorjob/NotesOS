'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import { GenerateTestForm } from '@/components/ai/GenerateTestForm';
import { Select } from '@/components/ui/Select';
import { Skeleton } from '@/components/feedback/Skeleton';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Icon } from '@/components/ui/Icon';
import { useToast } from '@/components/feedback/ToastProvider';
import { apiClient } from '@/lib/api';
import { api } from '@/lib/api';

interface Course { id: string; code: string; name: string; }
interface Topic  { id: string; title: string; week_number?: number; }

function GenerateTestContent() {
  const router = useRouter();
  const toast = useToast();
  const searchParams = useSearchParams();
  const courseParam = searchParams.get('course') ?? '';

  const [courses, setCourses]         = useState<Course[]>([]);
  const [selectedCourse, setSelCourse] = useState(courseParam);
  const [topics, setTopics]           = useState<Topic[]>([]);
  const [loading, setLoading]         = useState(false);
  const [generating, setGenerating]   = useState(false);

  useEffect(() => {
    apiClient.get('/api/courses').then((r) => {
      const all = r.data.courses ?? [];
      setCourses(all);
      if (!selectedCourse && all.length === 1) setSelCourse(all[0].id);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!selectedCourse) return;
    setLoading(true);
    apiClient.get(`/api/courses/${selectedCourse}/topics`)
      .then((r) => setTopics(r.data.topics ?? r.data ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [selectedCourse]);

  const handleGenerate = async (config: { topicIds: string[]; questionCount: number; difficulty: string; questionTypes: string[] }) => {
    if (!selectedCourse) { toast.error('Select a course first.'); return; }
    setGenerating(true);
    try {
      const res = await api.ai.generateTest(selectedCourse, {
        topic_ids: config.topicIds,
        question_count: config.questionCount,
        difficulty: config.difficulty,
        question_types: config.questionTypes,
      });
      const testId = res.data.id;
      router.push(`/practice/${testId}`);
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? 'Failed to generate test.');
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="px-4 md:px-8 py-6 max-w-lg mx-auto">
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1.5 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors mb-8"
      >
        <Icon name="arrow_back" size="xs" /> Practice
      </button>

      <h1 className="font-display font-bold text-2xl text-[var(--text-primary)] mb-1">Generate Test</h1>
      <p className="text-sm text-[var(--text-secondary)] mb-8">
        AI will create a personalised practice test from your materials.
      </p>

      {courses.length > 1 && (
        <Select
          label="Course"
          value={selectedCourse}
          onChange={(e) => setSelCourse(e.target.value)}
          options={courses.map((c) => ({ value: c.id, label: `${c.code} — ${c.name}` }))}
          placeholder="Select a course"
          containerClassName="mb-8"
        />
      )}

      {selectedCourse ? (
        loading ? (
          <div className="flex flex-col gap-4">
            {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-12" />)}
          </div>
        ) : topics.length === 0 ? (
          <EmptyState icon="topic" title="No topics found" body="Add topics to this course before generating a test." />
        ) : (
          <GenerateTestForm
            topics={topics.map((t) => ({ id: t.id, title: t.title, weekNumber: t.week_number }))}
            onGenerate={handleGenerate}
            loading={generating}
          />
        )
      ) : (
        <EmptyState icon="school" title="Select a course" body="Choose a course to pick topics and configure your test." />
      )}
    </div>
  );
}

export default function GenerateTestPage() {
  return (
    <Suspense fallback={<div className="p-8"><Skeleton className="h-8 w-48 mb-6" variant="text" /></div>}>
      <GenerateTestContent />
    </Suspense>
  );
}
