/**
 * Course Progress Page
 * Overall mastery, streak, topic progress, recommendations
 */

'use client';

import { useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Flame, Clock, Target, BookOpen } from 'lucide-react';
import { useCourseStore } from '@/stores/courses';
import { useProgressStore } from '@/stores/progress';
import { MainLayout } from '@/components/layout';
import { GlassCard, Button } from '@/components/ui';

export default function ProgressPage() {
    const params = useParams();
    const router = useRouter();
    const courseId = params.courseId as string;

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

    useEffect(() => {
        selectCourse(courseId);
    }, [courseId, selectCourse]);

    useEffect(() => {
        if (courseId) {
            fetchStreak(courseId);
            fetchCourseProgress(courseId);
            fetchTopicsProgress(courseId);
            fetchRecommendations(courseId);
        }
        return () => clearCourseProgress();
    }, [courseId, fetchCourseProgress, fetchTopicsProgress, fetchRecommendations, fetchStreak, clearCourseProgress]);

    const getMasteryColor = (level: number) => {
        if (level < 30) return 'var(--error)';
        if (level < 70) return 'var(--accent-secondary)';
        return 'var(--success)';
    };

    const topicIdToTitle = (topicId: string) => {
        const topic = currentCourse?.topics?.find((t) => t.id === topicId);
        return topic?.title ?? topicId.slice(0, 8);
    };

    if (!currentCourse) {
        return (
            <MainLayout>
                <div className="flex items-center justify-center min-h-[60vh]">
                    <p className="text-[var(--text-tertiary)]">Loading...</p>
                </div>
            </MainLayout>
        );
    }

    return (
        <MainLayout
            currentCourse={{ id: currentCourse.id, code: currentCourse.code, name: currentCourse.name }}
            streak={streak}
        >
            <div className="max-w-4xl mx-auto px-8 md:px-20 py-12">
                <button
                    onClick={() => router.push(`/courses/${courseId}`)}
                    className="flex items-center gap-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] mb-6 transition-colors"
                >
                    <ArrowLeft className="w-4 h-4" />
                    Back to {currentCourse.code}
                </button>

                <h1 className="text-2xl font-semibold text-[var(--text-primary)] mb-8">Your Progress</h1>

                {error && (
                    <div className="mb-6 px-4 py-3 bg-[var(--error)]/10 border border-[var(--error)]/20 rounded-lg">
                        <p className="text-sm text-[var(--error)]">{error}</p>
                    </div>
                )}

                {isLoading ? (
                    <GlassCard className="p-8 text-center">
                        <p className="text-[var(--text-tertiary)]">Loading progress...</p>
                    </GlassCard>
                ) : courseProgress ? (
                    <div className="space-y-6">
                        {/* Overview cards */}
                        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                            <GlassCard className="p-5">
                                <div className="flex items-center gap-3 mb-2">
                                    <Flame className="w-5 h-5 text-[var(--accent-primary)]" />
                                    <span className="text-sm text-[var(--text-tertiary)]">Streak</span>
                                </div>
                                <p className="text-2xl font-semibold text-[var(--text-primary)]">
                                    {courseProgress.current_streak} day{courseProgress.current_streak !== 1 ? 's' : ''}
                                </p>
                            </GlassCard>
                            <GlassCard className="p-5">
                                <div className="flex items-center gap-3 mb-2">
                                    <Target className="w-5 h-5 text-[var(--accent-primary)]" />
                                    <span className="text-sm text-[var(--text-tertiary)]">Mastery</span>
                                </div>
                                <p className="text-2xl font-semibold text-[var(--text-primary)]">
                                    {Math.round(courseProgress.overall_mastery * 100)}%
                                </p>
                            </GlassCard>
                            <GlassCard className="p-5">
                                <div className="flex items-center gap-3 mb-2">
                                    <Clock className="w-5 h-5 text-[var(--accent-primary)]" />
                                    <span className="text-sm text-[var(--text-tertiary)]">Study time</span>
                                </div>
                                <p className="text-2xl font-semibold text-[var(--text-primary)]">
                                    {Math.floor(courseProgress.total_study_time / 60)}m
                                </p>
                            </GlassCard>
                            <GlassCard className="p-5">
                                <div className="flex items-center gap-3 mb-2">
                                    <BookOpen className="w-5 h-5 text-[var(--accent-primary)]" />
                                    <span className="text-sm text-[var(--text-tertiary)]">Topics mastered</span>
                                </div>
                                <p className="text-2xl font-semibold text-[var(--text-primary)]">
                                    {courseProgress.topics_mastered} / {courseProgress.topics_count}
                                </p>
                            </GlassCard>
                        </div>

                        {/* Topic progress */}
                        {topicsProgress.length > 0 && (
                            <GlassCard>
                                <h2 className="text-lg font-medium text-[var(--text-primary)] mb-4">Topic progress</h2>
                                <div className="space-y-3">
                                    {topicsProgress.map((tp) => (
                                        <Link
                                            key={tp.topic_id}
                                            href={`/courses/${courseId}/topics/${tp.topic_id}`}
                                            className="block p-3 rounded-lg hover:bg-[var(--bg-sunken)] transition-colors"
                                        >
                                            <div className="flex items-center justify-between gap-4 mb-2">
                                                <span className="text-sm font-medium text-[var(--text-primary)]">
                                                    {topicIdToTitle(tp.topic_id)}
                                                </span>
                                                <span className="text-xs text-[var(--text-tertiary)]">
                                                    {Math.round(tp.mastery_level * 100)}%
                                                </span>
                                            </div>
                                            <div className="h-1.5 bg-[var(--bg-sunken)] rounded-full overflow-hidden">
                                                <div
                                                    className="h-full transition-all duration-300"
                                                    style={{
                                                        width: `${Math.round(tp.mastery_level * 100)}%`,
                                                        backgroundColor: getMasteryColor(tp.mastery_level * 100),
                                                    }}
                                                />
                                            </div>
                                        </Link>
                                    ))}
                                </div>
                            </GlassCard>
                        )}

                        {/* Recommendations */}
                        {recommendations.length > 0 && (
                            <GlassCard>
                                <h2 className="text-lg font-medium text-[var(--text-primary)] mb-4">Recommendations</h2>
                                <ul className="space-y-2">
                                    {recommendations.map((rec) => (
                                        <li key={rec.topic_id}>
                                            <Link
                                                href={`/courses/${courseId}/topics/${rec.topic_id}`}
                                                className="flex items-start gap-3 p-3 rounded-lg hover:bg-[var(--bg-sunken)] transition-colors"
                                            >
                                                <span
                                                    className={`text-xs font-medium px-2 py-0.5 rounded ${
                                                        rec.priority === 'high'
                                                            ? 'bg-[var(--error)]/20 text-[var(--error)]'
                                                            : rec.priority === 'medium'
                                                            ? 'bg-[var(--accent-secondary)]/20 text-[var(--accent-secondary)]'
                                                            : 'bg-[var(--bg-sunken)] text-[var(--text-tertiary)]'
                                                    }`}
                                                >
                                                    {rec.priority}
                                                </span>
                                                <div>
                                                    <p className="text-sm font-medium text-[var(--text-primary)]">
                                                        {topicIdToTitle(rec.topic_id)}
                                                    </p>
                                                    <p className="text-xs text-[var(--text-tertiary)] mt-0.5">
                                                        {rec.reason}
                                                    </p>
                                                </div>
                                            </Link>
                                        </li>
                                    ))}
                                </ul>
                            </GlassCard>
                        )}

                        {topicsProgress.length === 0 && recommendations.length === 0 && (
                            <GlassCard className="p-12 text-center">
                                <p className="text-[var(--text-secondary)] mb-2">No progress data yet</p>
                                <p className="text-sm text-[var(--text-tertiary)] mb-4">
                                    Study topics and take quizzes to see your progress here.
                                </p>
                                <Button variant="primary" onClick={() => router.push(`/courses/${courseId}`)}>
                                    Go to course
                                </Button>
                            </GlassCard>
                        )}
                    </div>
                ) : (
                    <GlassCard className="p-12 text-center">
                        <p className="text-[var(--text-tertiary)]">Unable to load progress.</p>
                    </GlassCard>
                )}
            </div>
        </MainLayout>
    );
}
