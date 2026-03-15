'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { CourseCard } from '@/components/cards/CourseCard';
import { SemesterGroupHeader } from '@/components/cards/SemesterGroupHeader';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Skeleton, SkeletonCard } from '@/components/feedback/Skeleton';
import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { apiClient } from '@/lib/api';

interface Course {
  id: string;
  code: string;
  name: string;
  semester?: string;
  semester_id?: string;
  member_count?: number;
  completion_percentage?: number;
  last_studied?: string | null;
}

interface Semester {
  id: string;
  name: string;
  start_date?: string;
  end_date?: string;
  member_count?: number;
}

export default function CoursesPage() {
  const router = useRouter();
  const [courses, setCourses]     = useState<Course[]>([]);
  const [semesters, setSemesters] = useState<Semester[]>([]);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState('');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [coursesRes, semestersRes] = await Promise.all([
          apiClient.get('/api/courses'),
          apiClient.get('/api/semesters').catch(() => ({ data: { semesters: [] } })),
        ]);
        setCourses(coursesRes.data.courses ?? []);
        setSemesters(semestersRes.data.semesters ?? []);
      } catch {
        setError('Failed to load courses.');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="px-4 md:px-8 py-6 max-w-4xl mx-auto">
        <Skeleton className="h-7 w-40 mb-6" variant="text" />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {[...Array(4)].map((_, i) => <SkeletonCard key={i} />)}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <EmptyState
        icon="error_outline"
        title="Something went wrong"
        body={error}
        ctaLabel="Retry"
        onCta={() => { setLoading(true); setError(''); }}
      />
    );
  }

  if (courses.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] px-6 text-center">
        <div className="w-20 h-20 rounded-3xl bg-[var(--color-primary-muted)] flex items-center justify-center mb-6">
          <Icon name="school" size="xl" className="text-[var(--color-primary)]" />
        </div>
        <h1 className="font-display font-bold text-2xl text-[var(--text-primary)] mb-3">
          Welcome to NoteOS
        </h1>
        <p className="text-sm text-[var(--text-secondary)] max-w-[300px] leading-relaxed mb-8">
          Join a semester with an invite code, or start by creating your first course.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 w-full max-w-xs">
          <Button
            variant="primary"
            size="md"
            onClick={() => router.push('/semesters/join')}
            iconLeft="group_add"
            fullWidth
          >
            Join Semester
          </Button>
          <Button
            variant="secondary"
            size="md"
            onClick={() => router.push('/courses/new')}
            iconLeft="add"
            fullWidth
          >
            Create Course
          </Button>
        </div>
      </div>
    );
  }

  // Group courses by semester
  const semesterMap = new Map(semesters.map((s) => [s.id, s]));
  const bySemester: Record<string, Course[]> = {};
  const ungrouped: Course[] = [];

  for (const course of courses) {
    if (course.semester_id && semesterMap.has(course.semester_id)) {
      const key = course.semester_id;
      bySemester[key] = bySemester[key] ?? [];
      bySemester[key].push(course);
    } else {
      ungrouped.push(course);
    }
  }

  return (
    <div className="px-4 md:px-8 py-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="font-display font-bold text-xl text-[var(--text-primary)]">My Courses</h1>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => router.push('/semesters/join')}
            iconLeft="group_add"
          >
            Join
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => router.push('/courses/new')}
            iconLeft="add"
          >
            New
          </Button>
        </div>
      </div>

      {/* Grouped by semester */}
      {Object.entries(bySemester).map(([semId, semCourses]) => {
        const sem = semesterMap.get(semId)!;
        return (
          <div key={semId} className="mb-8">
            <SemesterGroupHeader
              id={sem.id}
              name={sem.name}
              startDate={sem.start_date}
              endDate={sem.end_date}
              memberCount={sem.member_count}
              courseCount={semCourses.length}
              className="mb-3"
            />
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {semCourses.map((c) => (
                <CourseCard
                  key={c.id}
                  id={c.id}
                  code={c.code}
                  name={c.name}
                  semester={c.semester}
                  memberCount={c.member_count}
                  completionPercentage={c.completion_percentage}
                  lastStudied={c.last_studied}
                />
              ))}
            </div>
          </div>
        );
      })}

      {/* Ungrouped courses */}
      {ungrouped.length > 0 && (
        <div className={Object.keys(bySemester).length > 0 ? 'mt-6' : ''}>
          {Object.keys(bySemester).length > 0 && (
            <p className="text-xs font-bold uppercase tracking-widest text-[var(--text-tertiary)] mb-3">
              Other Courses
            </p>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {ungrouped.map((c) => (
              <CourseCard
                key={c.id}
                id={c.id}
                code={c.code}
                name={c.name}
                semester={c.semester}
                memberCount={c.member_count}
                completionPercentage={c.completion_percentage}
                lastStudied={c.last_studied}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
