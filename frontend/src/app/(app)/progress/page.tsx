'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useCourseStore } from '@/stores/courses';
import { api } from '@/lib/api';
import { ProgressBar } from '@/components/ui/ProgressBar';
import { Badge } from '@/components/ui/Badge';
import { Spinner } from '@/components/ui/Spinner';

interface RecentAttempt {
  attempt_id: string;
  test_id: string;
  title: string;
  score_pct: number;
  completed_at: string;
}

interface CourseProgressData {
  course_id: string;
  overall_mastery: number;
  total_study_time: number;
  current_streak: number;
  topics_count: number;
  topics_mastered: number;
}

interface TopicProgressData {
  topic_id: string;
  mastery_level: number;
  total_study_time: number;
  avg_score: number | null;
}

function StatCard({ label, value, unit, icon }: { label: string; value: string | number; unit?: string; icon?: string }) {
  return (
    <div className="bg-white rounded-2xl border border-[#dedad4] p-5">
      <p className="text-xs text-[#9e9a94] uppercase tracking-wide mb-1">
        {icon && <span className="mr-1">{icon}</span>}{label}
      </p>
      <p className="text-2xl font-semibold text-[#1a1917]">
        {value}
        {unit && <span className="text-sm font-normal text-[#6b6762] ml-1">{unit}</span>}
      </p>
    </div>
  );
}

function statusBadge(mastery: number) {
  const pct = Math.round(mastery * 100);
  if (pct === 0) return <Badge variant="muted">Not started</Badge>;
  if (pct < 60) return <Badge variant="warning">Needs work</Badge>;
  return <Badge variant="success">Good</Badge>;
}

export default function ProgressPage() {
  const { courses, fetchCourses, selectCourse } = useCourseStore();

  const [allCourseProgress, setAllCourseProgress] = useState<Record<string, CourseProgressData>>({});
  const [allTopicsProgress, setAllTopicsProgress] = useState<Record<string, TopicProgressData[]>>({});
  const [loadingProgress, setLoadingProgress] = useState(false);

  const [recentAttempts, setRecentAttempts] = useState<RecentAttempt[]>([]);
  const [overallAvgScore, setOverallAvgScore] = useState<number | null>(null);
  const [loadingTests, setLoadingTests] = useState(false);

  const hasFetched = useRef(false);

  useEffect(() => {
    fetchCourses();
  }, [fetchCourses]);

  useEffect(() => {
    if (courses.length === 0 || hasFetched.current) return;
    hasFetched.current = true;
    loadAllProgress();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [courses.length]);

  useEffect(() => {
    setLoadingTests(true);
    // Fetch recent attempts for the quiz history list
    api.ai.getRecentAttempts(10)
      .then((res) => setRecentAttempts(res.data?.attempts ?? []))
      .catch(() => {})
      .finally(() => setLoadingTests(false));
  }, []);

  // Aggregate average score across all courses once courses are loaded
  useEffect(() => {
    if (courses.length === 0) return;
    Promise.allSettled(courses.map((c) => api.ai.getTestStats(c.id)))
      .then((results) => {
        const valid = results
          .filter((r) => r.status === 'fulfilled')
          .map((r) => (r as PromiseFulfilledResult<any>).value.data);
        if (valid.length > 0) {
          const avg = valid.reduce((s: number, d: any) => s + (d.average_score ?? 0), 0) / valid.length;
          setOverallAvgScore(Math.round(avg));
        }
      })
      .catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [courses.length]);

  async function loadAllProgress() {
    setLoadingProgress(true);
    const progressMap: Record<string, CourseProgressData> = {};
    const topicsMap: Record<string, TopicProgressData[]> = {};

    await Promise.all(
      courses.map(async (course) => {
        if (!course.topics?.length) {
          await selectCourse(course.id).catch(() => {});
        }
        try {
          const [cp, tp] = await Promise.all([
            api.progress.getCourseProgress(course.id),
            api.progress.getTopicsProgress(course.id),
          ]);
          progressMap[course.id] = cp.data;
          topicsMap[course.id] = tp.data?.topics ?? tp.data ?? [];
        } catch { /* keep going */ }
      })
    );

    setAllCourseProgress(progressMap);
    setAllTopicsProgress(topicsMap);
    setLoadingProgress(false);
  }

  const maxStreak = Object.values(allCourseProgress).reduce((m, p) => Math.max(m, p.current_streak ?? 0), 0);
  const totalStudyTimeSec = Object.values(allCourseProgress).reduce((s, p) => s + (p.total_study_time ?? 0), 0);
  const studiedTopics = Object.values(allTopicsProgress).flat().filter((t) => t.mastery_level > 0).length;
  const totalTopics = Object.values(allCourseProgress).reduce((s, p) => s + (p.topics_count ?? 0), 0);
  const avgScore = overallAvgScore ?? null;

  const isLoading = loadingProgress && Object.keys(allCourseProgress).length === 0;

  return (
    <div className="max-w-3xl mx-auto px-4 md:px-6 py-8 space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-[#1a1917]">Progress</h1>
        <p className="text-xs text-[#9e9a94] mt-0.5">Personal — only visible to you</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard icon="🔥" label="Day streak" value={maxStreak} unit="days" />
        <StatCard label="Study time" value={Math.round(totalStudyTimeSec / 3600)} unit="hrs" />
        <StatCard label="Avg quiz score" value={avgScore != null ? `${avgScore}%` : '—'} />
        <StatCard label="Topics studied" value={`${studiedTopics}/${totalTopics}`} />
      </div>

      {/* Per-course breakdown */}
      {isLoading && <div className="flex justify-center py-8"><Spinner size="lg" /></div>}

      {!isLoading && courses.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-sm font-semibold text-[#6b6762] uppercase tracking-wide">Course Breakdown</h2>

          {courses.map((course) => {
            const cp = allCourseProgress[course.id];
            const topicsForCourse = course.topics ?? [];
            const topicProgress = allTopicsProgress[course.id] ?? [];
            const studiedCount = topicProgress.filter((t) => t.mastery_level > 0).length;

            return (
              <div key={course.id} className="bg-white rounded-2xl border border-[#dedad4] p-5 space-y-4">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-[#1a1917]">{course.code} — {course.name}</p>
                    <p className="text-xs text-[#6b6762] mt-0.5">{studiedCount} / {topicsForCourse.length} topics studied</p>
                  </div>
                  {cp && (
                    <p className="text-xs text-[#9e9a94] shrink-0">{Math.round((cp.overall_mastery ?? 0) * 100)}% overall</p>
                  )}
                </div>

                {topicsForCourse.length === 0 && (
                  <p className="text-xs text-[#9e9a94] italic">No topics yet.</p>
                )}

                <div className="space-y-3">
                  {topicsForCourse.map((topic) => {
                    const tp = topicProgress.find((p) => p.topic_id === topic.id);
                    const mastery = tp?.mastery_level ?? 0;
                    const pct = Math.round(mastery * 100);
                    return (
                      <div key={topic.id} className="space-y-1.5">
                        <div className="flex items-center justify-between gap-2">
                          <Link
                            href={`/courses/${course.id}/topics/${topic.id}`}
                            className="text-sm text-[#1a1917] hover:underline truncate flex-1"
                          >
                            {topic.title}
                          </Link>
                          <div className="flex items-center gap-2 shrink-0">
                            <span className="text-xs text-[#6b6762]">{pct}%</span>
                            {statusBadge(mastery)}
                          </div>
                        </div>
                        <ProgressBar value={pct} size="sm" />
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Recent quizzes */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold text-[#6b6762] uppercase tracking-wide">Recent Quizzes</h2>
        {loadingTests && <Spinner size="sm" />}
        {!loadingTests && recentAttempts.length === 0 && (
          <p className="text-sm text-[#9e9a94]">No quizzes taken yet.</p>
        )}
        <div className="space-y-2">
          {recentAttempts.map((a) => (
            <div
              key={a.attempt_id}
              className="bg-white border border-[#dedad4] rounded-xl px-4 py-3 flex items-center justify-between gap-3"
            >
              <div>
                <p className="text-sm font-medium text-[#1a1917]">{a.title}</p>
                <p className="text-xs text-[#9e9a94]">
                  {new Date(a.completed_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                </p>
              </div>
              <Badge variant={a.score_pct >= 70 ? 'success' : a.score_pct >= 50 ? 'warning' : 'error'}>
                {Math.round(a.score_pct)}%
              </Badge>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
