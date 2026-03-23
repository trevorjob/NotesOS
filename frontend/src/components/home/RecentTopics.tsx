'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useCourseStore } from '@/stores/courses';

interface RecentEntry { topicId: string; courseId: string }

export function RecentTopics() {
  const courses = useCourseStore((s) => s.courses);
  const [recents, setRecents] = useState<RecentEntry[]>([]);

  useEffect(() => {
    try {
      const stored = localStorage.getItem('notesos-recent-topics');
      if (stored) setRecents(JSON.parse(stored));
    } catch { /* ignore */ }
  }, []);

  // Resolve topic/course info from the store
  const resolved = recents
    .map(({ topicId, courseId }) => {
      const course = courses.find((c) => c.id === courseId);
      const topic = course?.topics?.find((t) => t.id === topicId);
      if (!course || !topic) return null;
      return { topicId, courseId, title: topic.title, courseCode: course.code };
    })
    .filter(Boolean)
    .slice(0, 3) as Array<{ topicId: string; courseId: string; title: string; courseCode: string }>;

  // Fallback: first 3 topics if no recents yet
  const fallback = courses
    .flatMap((c) => (c.topics ?? []).map((t) => ({ topicId: t.id, courseId: c.id, title: t.title, courseCode: c.code })))
    .slice(0, 3);

  const items = resolved.length > 0 ? resolved : fallback;

  if (items.length === 0) return null;

  return (
    <div>
      <h2 className="text-sm font-semibold text-[#6b6762] uppercase tracking-wide mb-3">
        {resolved.length > 0 ? 'Recently Visited' : 'Recent Topics'}
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {items.map((t) => (
          <Link
            key={t.topicId}
            href={`/courses/${t.courseId}/topics/${t.topicId}`}
            className="bg-white rounded-xl border border-[#dedad4] px-4 py-3 hover:border-[#9e9a94] transition-colors"
          >
            <p className="text-sm font-medium text-[#1a1917] truncate">{t.title}</p>
            <p className="text-xs text-[#9e9a94] mt-0.5">{t.courseCode}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
