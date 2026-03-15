'use client';

import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { MetricCard } from '@/components/cards/MetricCard';
import { LinearProgressBar } from '@/components/data-display/LinearProgressBar';
import { AIRecommendationBlock } from '@/components/ai/AIRecommendationBlock';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Skeleton } from '@/components/feedback/Skeleton';
import { Icon } from '@/components/ui/Icon';
import { useCourseStore } from '@/stores/courses';
import { useProgressStore } from '@/stores/progress';

export default function CourseProgressPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const router = useRouter();

  const { currentCourse, selectCourse } = useCourseStore();
  const {
    courseProgress,
    topicsProgress,
    recommendations,
    streak,
    isLoading,
    error,
    fetchCourseProgress,
    fetchTopicsProgress,
    fetchRecommendations,
    fetchStreak,
    clearCourseProgress,
  } = useProgressStore();

  useEffect(() => { selectCourse(courseId); }, [courseId, selectCourse]);

  useEffect(() => {
    if (!courseId) return;
    fetchStreak(courseId);
    fetchCourseProgress(courseId);
    fetchTopicsProgress(courseId);
    fetchRecommendations(courseId);
    return () => clearCourseProgress();
  }, [courseId, fetchCourseProgress, fetchTopicsProgress, fetchRecommendations, fetchStreak, clearCourseProgress]);

  const topicTitle = (id: string) =>
    currentCourse?.topics?.find((t: any) => t.id === id)?.title ?? id.slice(0, 8);

  if (isLoading) {
    return (
      <div className="px-4 md:px-8 py-6 max-w-4xl mx-auto">
        <Skeleton className="h-7 w-48 mb-6" variant="text" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-24" />)}
        </div>
        <Skeleton className="h-48" />
      </div>
    );
  }

  return (
    <div className="px-4 md:px-8 py-6 max-w-4xl mx-auto">
      <button
        onClick={() => router.push(`/courses/${courseId}`)}
        className="flex items-center gap-1.5 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors mb-6"
      >
        <Icon name="arrow_back" size="xs" />
        {currentCourse?.code ?? 'Course'}
      </button>

      <h1 className="font-display font-bold text-2xl text-[var(--text-primary)] mb-6">
        Progress Dashboard
      </h1>

      {error && (
        <div className="mb-6 px-4 py-3 bg-[var(--error-bg)] rounded-xl text-sm text-[var(--error-text)]">
          {error}
        </div>
      )}

      {!courseProgress ? (
        <EmptyState
          icon="trending_up"
          title="No progress yet"
          body="Study topics and take practice tests to build your progress data."
          ctaLabel="Go to course"
          onCta={() => router.push(`/courses/${courseId}`)}
        />
      ) : (
        <div className="flex flex-col gap-6">
          {/* Overview metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MetricCard icon="local_fire_department" value={`${courseProgress.current_streak}d`} label="Study streak" iconFilled />
            <MetricCard icon="target" value={`${Math.round(courseProgress.overall_mastery * 100)}%`} label="Overall mastery" />
            <MetricCard icon="schedule" value={`${Math.floor(courseProgress.total_study_time / 60)}m`} label="Study time" />
            <MetricCard icon="school" value={`${courseProgress.topics_mastered}/${courseProgress.topics_count}`} label="Topics mastered" />
          </div>

          {/* AI Recommendations */}
          {recommendations.length > 0 && (
            <section>
              <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--text-tertiary)] mb-3">
                Recommendations
              </h2>
              <div className="flex flex-col gap-3">
                {recommendations.slice(0, 3).map((rec: any) => (
                  <AIRecommendationBlock
                    key={rec.topic_id}
                    topicTitle={topicTitle(rec.topic_id)}
                    topicId={rec.topic_id}
                    courseId={courseId}
                    reason={rec.reason}
                  />
                ))}
              </div>
            </section>
          )}

          {/* Topic breakdown */}
          {topicsProgress.length > 0 && (
            <section>
              <h2 className="text-sm font-bold uppercase tracking-widest text-[var(--text-tertiary)] mb-3">
                Topic Breakdown
              </h2>
              <div className="flex flex-col gap-2">
                {topicsProgress.map((tp: any) => {
                  const pct = Math.round(tp.mastery_level * 100);
                  return (
                    <Link
                      key={tp.topic_id}
                      href={`/courses/${courseId}/topics/${tp.topic_id}`}
                      className="flex items-center gap-4 p-4 rounded-xl border border-[var(--border-base)] bg-[var(--bg-elevated)] hover:border-[var(--color-primary-muted)] transition-colors"
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-[var(--text-primary)] truncate mb-2">
                          {topicTitle(tp.topic_id)}
                        </p>
                        <LinearProgressBar value={pct} size="thin" />
                      </div>
                      <span className="text-sm font-bold text-[var(--text-secondary)] flex-shrink-0">{pct}%</span>
                    </Link>
                  );
                })}
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  );
}
