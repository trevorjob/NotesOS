'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { useCourseStore } from '@/stores/courses';
import { useProgressStore } from '@/stores/progress';
import { Button } from '@/components/ui/Button';
import { ProgressBar } from '@/components/ui/ProgressBar';

export function ContinueStudyingCard() {
  const courses = useCourseStore((s) => s.courses);
  const { topicsProgress, fetchTopicsProgress } = useProgressStore();

  // Find last-studied topic from localStorage
  let lastTopicId: string | null = null;
  let lastCourseId: string | null = null;
  try {
    lastTopicId = typeof window !== 'undefined' ? localStorage.getItem('last_topic_id') : null;
    lastCourseId = typeof window !== 'undefined' ? localStorage.getItem('last_course_id') : null;
  } catch { /* ignore */ }

  // Resolve topic + course from store
  let topic: { id: string; title: string } | undefined;
  let course = courses[0];

  if (lastTopicId && lastCourseId) {
    const foundCourse = courses.find((c) => c.id === lastCourseId);
    if (foundCourse) {
      course = foundCourse;
      topic = foundCourse.topics?.find((t) => t.id === lastTopicId);
    }
  }

  // Fallback: first topic of first course
  if (!topic && course?.topics?.length) {
    topic = course.topics[0];
  }

  const courseId = course?.id;

  // Fetch topic-level progress for the course so we can show mastery
  useEffect(() => {
    if (courseId) fetchTopicsProgress(courseId).catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [courseId]);

  if (!topic || !course) {
    return (
      <div className="bg-white rounded-2xl border border-[#dedad4] p-6">
        <p className="text-sm text-[#6b6762]">No topics yet — add a course to get started.</p>
      </div>
    );
  }

  const href = `/courses/${course.id}/topics/${topic.id}`;
  const tp = topicsProgress.find((p) => p.topic_id === topic!.id);
  const mastery = tp ? Math.round(tp.mastery_level * 100) : 0;

  return (
    <div className="rounded-2xl border border-[#dedad4] bg-white p-6">
      <p className="mb-1 text-xs font-medium tracking-wide text-[#9e9a94] uppercase">Continue studying</p>
      <h3 className="mb-0.5 text-base font-semibold text-[#1a1917]">{topic.title}</h3>
      <p className="mb-4 text-sm text-[#6b6762]">{course.code} · {course.name}</p>

      <ProgressBar value={mastery} size="sm" showLabel className="mb-4" />

      <Link href={href}>
        <Button size="sm">Resume</Button>
      </Link>
    </div>
  );
}
