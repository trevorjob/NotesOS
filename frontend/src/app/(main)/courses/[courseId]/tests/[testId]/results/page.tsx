/**
 * Test Results Page
 * Show score and per-answer feedback (or "Grading in progress")
 */

'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, CheckCircle, Loader2 } from 'lucide-react';
import { useCourseStore } from '@/stores/courses';
import { useProgressStore } from '@/stores/progress';
import { useTestsStore } from '@/stores/tests';
import { MainLayout } from '@/components/layout';
import { GlassCard, Button } from '@/components/ui';

export default function TestResultsPage() {
    const params = useParams();
    const router = useRouter();
    const searchParams = useSearchParams();
    const courseId = params.courseId as string;
    const testId = params.testId as string;
    const attemptId = searchParams.get('attemptId');

    const { currentCourse, selectCourse } = useCourseStore();
    const { streak, fetchStreak } = useProgressStore();
    const { results, getTestResults } = useTestsStore();

    const [pollCount, setPollCount] = useState(0);

    useEffect(() => {
        selectCourse(courseId);
    }, [courseId, selectCourse]);

    useEffect(() => {
        if (courseId) fetchStreak(courseId);
    }, [courseId, fetchStreak]);

    useEffect(() => {
        if (!attemptId) return;
        getTestResults(attemptId).catch(() => {});
    }, [attemptId]);

    // Keep polling while grading incomplete (no answers yet or completed_at null)
    const gradingIncomplete = results && (results.answers.length === 0 || results.completed_at == null);
    useEffect(() => {
        if (!attemptId || !gradingIncomplete) return;
        const t = setTimeout(() => {
            setPollCount((c) => c + 1);
            getTestResults(attemptId).catch(() => {});
        }, 3000);
        return () => clearTimeout(t);
    }, [attemptId, gradingIncomplete, pollCount, getTestResults]);

    if (!currentCourse) {
        return (
            <MainLayout>
                <div className="flex items-center justify-center min-h-[60vh]">
                    <p className="text-[var(--text-tertiary)]">Loading...</p>
                </div>
            </MainLayout>
        );
    }

    const gradingInProgress = attemptId && results !== null && (results.answers.length === 0 || results.completed_at == null);
    const hasResults = results && results.answers.length > 0;

    return (
        <MainLayout
            currentCourse={{ id: currentCourse.id, code: currentCourse.code, name: currentCourse.name }}
            streak={streak}
        >
            <div className="max-w-3xl mx-auto px-8 md:px-20 py-12">
                <Link
                    href={`/courses/${courseId}/tests`}
                    className="inline-flex items-center gap-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] mb-8 transition-colors"
                >
                    <ArrowLeft className="w-4 h-4" />
                    Back to tests
                </Link>

                <h1 className="text-2xl font-semibold text-[var(--text-primary)] mb-8">Test results</h1>

                {!attemptId ? (
                    <GlassCard className="p-8 text-center">
                        <p className="text-[var(--text-tertiary)]">No attempt ID. Start a test first.</p>
                        <Button variant="primary" className="mt-4" onClick={() => router.push(`/courses/${courseId}/tests`)}>
                            Go to tests
                        </Button>
                    </GlassCard>
                ) : gradingInProgress ? (
                    <GlassCard className="p-12 text-center">
                        <Loader2 className="w-12 h-12 animate-spin mx-auto mb-4 text-[var(--accent-primary)]" />
                        <p className="text-[var(--text-primary)] font-medium">Grading in progress</p>
                        <p className="text-sm text-[var(--text-tertiary)] mt-1">Results will appear shortly. This page will update automatically.</p>
                    </GlassCard>
                ) : hasResults ? (
                    <div className="space-y-6">
                        <GlassCard className="p-6">
                            <div className="flex items-center justify-between flex-wrap gap-4">
                                <div>
                                    <p className="text-sm text-[var(--text-tertiary)]">Score</p>
                                    <p className="text-3xl font-semibold text-[var(--text-primary)]">
                                        {results!.total_score.toFixed(1)} / {results!.max_score}
                                    </p>
                                </div>
                                <div className="flex items-center gap-2">
                                    {results!.completed_at != null ? (
                                        <span className="flex items-center gap-2 text-[var(--success)] font-medium">
                                            <CheckCircle className="w-6 h-6" />
                                            Completed
                                        </span>
                                    ) : (
                                        <span className="text-sm text-[var(--text-tertiary)]">Updating...</span>
                                    )}
                                </div>
                            </div>
                            {results!.completed_at == null && (
                                <p className="text-xs text-[var(--text-tertiary)] mt-2">Some questions still being graded. Results update automatically.</p>
                            )}
                        </GlassCard>

                        <h2 className="text-lg font-medium text-[var(--text-primary)]">Answer feedback</h2>
                        {results!.answers.map((a, i) => (
                            <GlassCard key={i} className="p-5">
                                <div className="flex items-start gap-3 mb-2">
                                    <span className="text-lg font-semibold text-[var(--accent-primary)]">
                                        {a.score.toFixed(0)} pts
                                    </span>
                                </div>
                                {a.feedback && (
                                    <p className="text-sm text-[var(--text-secondary)] mb-2">{a.feedback}</p>
                                )}
                                {a.encouragement && (
                                    <p className="text-sm text-[var(--text-tertiary)] italic">{a.encouragement}</p>
                                )}
                            </GlassCard>
                        ))}

                        <div className="flex gap-3">
                            <Button variant="primary" onClick={() => router.push(`/courses/${courseId}/tests`)}>
                                Take another test
                            </Button>
                            <Button variant="secondary" onClick={() => router.push(`/courses/${courseId}`)}>
                                Back to course
                            </Button>
                        </div>
                    </div>
                ) : results && results.answers.length === 0 ? (
                    <GlassCard className="p-8 text-center">
                        <p className="text-[var(--text-tertiary)]">No graded answers yet. Grading may still be in progress.</p>
                        <Button variant="primary" className="mt-4" onClick={() => getTestResults(attemptId)}>
                            Refresh results
                        </Button>
                    </GlassCard>
                ) : (
                    <GlassCard className="p-8 text-center">
                        <Loader2 className="w-8 h-8 animate-spin mx-auto text-[var(--text-tertiary)]" />
                        <p className="text-sm text-[var(--text-tertiary)] mt-2">Loading results...</p>
                    </GlassCard>
                )}
            </div>
        </MainLayout>
    );
}
