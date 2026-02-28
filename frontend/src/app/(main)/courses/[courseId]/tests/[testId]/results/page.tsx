/**
 * Test Results Page
 * Show score and per-answer feedback (or "Grading in progress")
 */

'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, CheckCircle, Loader2, Trophy } from 'lucide-react';
import { useCourseStore } from '@/stores/courses';
import { useProgressStore } from '@/stores/progress';
import { useTestsStore } from '@/stores/tests';
import { MainLayout } from '@/components/layout';

// ── Helpers ───────────────────────────────────────────────────────────────────

function scoreTextColor(pct: number): string {
    if (pct >= 80) return 'text-[var(--success)]';
    if (pct >= 60) return 'text-[#A07830]';
    return 'text-[var(--error)]';
}

function scoreBgBorder(pct: number): string {
    if (pct >= 80) return 'bg-[#6B8F71]/10 border-[#6B8F71]/20';
    if (pct >= 60) return 'bg-[#D4A853]/10 border-[#D4A853]/20';
    return 'bg-[var(--error)]/10 border-[var(--error)]/20';
}

function scoreBorderLeft(pct: number): string {
    if (pct >= 80) return 'border-l-[#6B8F71]';
    if (pct >= 60) return 'border-l-[#D4A853]';
    return 'border-l-[var(--error)]';
}

function scoreBarColor(pct: number): string {
    if (pct >= 80) return 'bg-[var(--success)]';
    if (pct >= 60) return 'bg-[#D4A853]';
    return 'bg-[var(--error)]';
}

// ── Skeleton card for grading state ──────────────────────────────────────────

function SkeletonCard() {
    return (
        <div className="rounded-xl border border-[var(--glass-border)] bg-[var(--bg-elevated)] p-5 animate-pulse">
            <div className="h-3 bg-[var(--bg-sunken)] rounded w-1/4 mb-4" />
            <div className="h-4 bg-[var(--bg-sunken)] rounded w-3/4 mb-2" />
            <div className="h-4 bg-[var(--bg-sunken)] rounded w-1/2" />
        </div>
    );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function TestResultsPage() {
    const params = useParams();
    const router = useRouter();
    const searchParams = useSearchParams();
    const courseId = params.courseId as string;
    const testId = params.testId as string;
    const attemptId = searchParams.get('attemptId');

    const { currentCourse, selectCourse } = useCourseStore();
    const { streak, fetchStreak } = useProgressStore();
    const { results, getTestResults, listenForGrading } = useTestsStore();

    const [gradingDone, setGradingDone] = useState(false);

    useEffect(() => { selectCourse(courseId); }, [courseId, selectCourse]);
    useEffect(() => { if (courseId) fetchStreak(courseId); }, [courseId, fetchStreak]);

    useEffect(() => {
        if (!attemptId) return;
        getTestResults(attemptId).catch(() => { });
    }, [attemptId]);

    useEffect(() => {
        if (!attemptId || !courseId || gradingDone) return;
        if (results?.completed_at != null) { setGradingDone(true); return; }
        const cleanup = listenForGrading(attemptId, courseId, () => setGradingDone(true));
        return cleanup;
    }, [attemptId, courseId, gradingDone, results?.completed_at]);

    if (!currentCourse) {
        return (
            <MainLayout>
                <div className="flex items-center justify-center min-h-[60vh]">
                    <Loader2 className="w-6 h-6 animate-spin text-[var(--text-tertiary)]" />
                </div>
            </MainLayout>
        );
    }

    const gradingInProgress =
        attemptId && results !== null &&
        (results.answers.length === 0 || results.completed_at == null);
    const hasResults = results && results.answers.length > 0;

    const totalPct =
        results && results.max_score > 0
            ? Math.round((results.total_score / results.max_score) * 100)
            : null;

    return (
        <MainLayout
            currentCourse={{ id: currentCourse.id, code: currentCourse.code, name: currentCourse.name }}
            streak={streak}
        >
            <div className="max-w-3xl mx-auto px-8 md:px-20 py-12">
                <Link
                    href={`/courses/${courseId}/tests`}
                    className="inline-flex items-center gap-2 text-sm text-[var(--text-tertiary)] hover:text-[var(--text-primary)] mb-8 transition-colors"
                >
                    <ArrowLeft className="w-4 h-4" />
                    Back to tests
                </Link>

                <h1 className="text-2xl font-semibold text-[var(--text-primary)] mb-8">Test results</h1>

                {/* ── No attempt ID ─────────────────────────────── */}
                {!attemptId ? (
                    <div className="rounded-xl border border-[var(--glass-border)] bg-[var(--bg-elevated)] p-10 text-center">
                        <p className="text-[var(--text-tertiary)] mb-4">No attempt ID. Start a test first.</p>
                        <button
                            onClick={() => router.push(`/courses/${courseId}/tests`)}
                            className="px-4 py-2 rounded-lg bg-[var(--accent-primary)] text-[var(--bg-elevated)] text-sm font-medium hover:bg-[var(--accent-hover)] transition-colors"
                        >
                            Go to tests
                        </button>
                    </div>

                    /* ── Grading in progress ────────────────────── */
                ) : gradingInProgress ? (
                    <div className="space-y-6">
                        <div className="rounded-xl border border-[var(--glass-border)] bg-[var(--bg-elevated)] p-8 text-center">
                            <div className="w-14 h-14 rounded-full bg-[var(--bg-sunken)] flex items-center justify-center mx-auto mb-4">
                                <Loader2 className="w-7 h-7 animate-spin text-[var(--text-tertiary)]" />
                            </div>
                            <p className="text-[var(--text-primary)] font-medium">Grading in progress</p>
                            <p className="text-sm text-[var(--text-tertiary)] mt-1">
                                Results will appear shortly — this page updates automatically.
                            </p>
                        </div>
                        <SkeletonCard />
                        <SkeletonCard />
                        <SkeletonCard />
                    </div>

                    /* ── Has results ───────────────────────────── */
                ) : hasResults ? (
                    <div className="space-y-6">
                        {/* Score card */}
                        <div className="rounded-xl border border-[var(--glass-border)] bg-[var(--bg-elevated)] p-6">
                            <div className="flex items-center gap-6">
                                <div className="w-16 h-16 rounded-full bg-[var(--bg-sunken)] flex items-center justify-center shrink-0">
                                    <Trophy className={`w-7 h-7 ${totalPct != null ? scoreTextColor(totalPct) : 'text-[var(--text-tertiary)]'}`} />
                                </div>
                                <div className="flex-1">
                                    <p className="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wider mb-1">
                                        Your score
                                    </p>
                                    <p className={`text-4xl font-bold ${totalPct != null ? scoreTextColor(totalPct) : 'text-[var(--text-primary)]'}`}>
                                        {totalPct != null ? `${totalPct}%` : '—'}
                                    </p>
                                    <p className="text-sm text-[var(--text-tertiary)] mt-0.5">
                                        {results!.total_score.toFixed(1)} / {results!.max_score} points
                                    </p>
                                </div>
                                <div className="shrink-0">
                                    {results!.completed_at != null ? (
                                        <span className="flex items-center gap-1.5 text-sm text-[var(--success)] font-medium">
                                            <CheckCircle className="w-4 h-4" />
                                            Completed
                                        </span>
                                    ) : (
                                        <span className="text-xs text-[var(--text-tertiary)] flex items-center gap-1.5">
                                            <Loader2 className="w-3 h-3 animate-spin" />
                                            Partial results
                                        </span>
                                    )}
                                </div>
                            </div>

                            {/* Score bar */}
                            {totalPct != null && (
                                <div className="mt-5 h-2 bg-[var(--bg-sunken)] rounded-full overflow-hidden">
                                    <div
                                        className={`h-full rounded-full transition-all duration-700 ${scoreBarColor(totalPct)}`}
                                        style={{ width: `${totalPct}%` }}
                                    />
                                </div>
                            )}

                            {results!.completed_at == null && (
                                <p className="text-xs text-[var(--text-tertiary)] mt-3">
                                    Some questions still being graded. Results update automatically.
                                </p>
                            )}
                        </div>

                        {/* Per-answer feedback */}
                        <h2 className="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wider">
                            Answer feedback
                        </h2>

                        {results!.answers.map((a, i) => {
                            const answerPct = results!.max_score > 0
                                ? Math.round((a.score / (results!.max_score / results!.answers.length)) * 100)
                                : null;
                            return (
                                <div
                                    key={i}
                                    className={`rounded-xl border bg-[var(--bg-elevated)] border-l-4 p-5 ${answerPct != null ? scoreBorderLeft(answerPct) : 'border-l-[var(--glass-border)]'
                                        } border-t border-r border-b border-[var(--glass-border)]`}
                                >
                                    <div className="flex items-start justify-between gap-3 mb-3">
                                        <span className="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wider">
                                            Question {i + 1}
                                        </span>
                                        {answerPct != null && (
                                            <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${scoreBgBorder(answerPct)} ${scoreTextColor(answerPct)}`}>
                                                {a.score.toFixed(0)} pts
                                            </span>
                                        )}
                                    </div>

                                    {a.feedback && (
                                        <p className="text-sm text-[var(--text-secondary)] leading-relaxed mb-2">
                                            {a.feedback}
                                        </p>
                                    )}

                                    {a.key_points_covered && a.key_points_covered.length > 0 && (
                                        <div className="mt-3">
                                            <p className="text-xs font-medium text-[var(--success)] mb-1">✓ Covered</p>
                                            <ul className="text-xs text-[var(--text-tertiary)] space-y-0.5 pl-3">
                                                {a.key_points_covered.map((pt, j) => (
                                                    <li key={j}>• {pt}</li>
                                                ))}
                                            </ul>
                                        </div>
                                    )}

                                    {a.key_points_missed && a.key_points_missed.length > 0 && (
                                        <div className="mt-2">
                                            <p className="text-xs font-medium text-[var(--error)] mb-1">✗ Missed</p>
                                            <ul className="text-xs text-[var(--text-tertiary)] space-y-0.5 pl-3">
                                                {a.key_points_missed.map((pt, j) => (
                                                    <li key={j}>• {pt}</li>
                                                ))}
                                            </ul>
                                        </div>
                                    )}

                                    {a.encouragement && (
                                        <p className="text-xs text-[var(--text-tertiary)] italic mt-3 pt-3 border-t border-[var(--glass-border)]">
                                            {a.encouragement}
                                        </p>
                                    )}
                                </div>
                            );
                        })}

                        {/* Actions */}
                        <div className="flex gap-3 pt-2">
                            <button
                                onClick={() => router.push(`/courses/${courseId}/tests`)}
                                className="px-5 py-2.5 rounded-lg bg-[var(--accent-primary)] text-[var(--bg-elevated)] text-sm font-medium hover:bg-[var(--accent-hover)] transition-colors"
                            >
                                Take another test
                            </button>
                            <button
                                onClick={() => router.push(`/courses/${courseId}`)}
                                className="px-5 py-2.5 rounded-lg border border-[#D6D3D1] text-[var(--text-secondary)] text-sm font-medium hover:bg-[var(--bg-sunken)] transition-colors"
                            >
                                Back to course
                            </button>
                        </div>
                    </div>

                    /* ── Empty results (no answers yet) ──────────── */
                ) : results && results.answers.length === 0 ? (
                    <div className="rounded-xl border border-[var(--glass-border)] bg-[var(--bg-elevated)] p-10 text-center">
                        <Loader2 className="w-8 h-8 animate-spin mx-auto mb-3 text-[var(--text-tertiary)]" />
                        <p className="text-[var(--text-secondary)] mb-4">No graded answers yet. Grading may still be in progress.</p>
                        <button
                            onClick={() => attemptId && getTestResults(attemptId)}
                            className="px-4 py-2 rounded-lg border border-[#D6D3D1] text-[var(--text-secondary)] text-sm font-medium hover:bg-[var(--bg-sunken)] transition-colors"
                        >
                            Refresh results
                        </button>
                    </div>

                    /* ── Loading ─────────────────────────────────── */
                ) : (
                    <div className="rounded-xl border border-[var(--glass-border)] bg-[var(--bg-elevated)] p-10 text-center">
                        <Loader2 className="w-8 h-8 animate-spin mx-auto mb-2 text-[var(--text-tertiary)]" />
                        <p className="text-sm text-[var(--text-tertiary)]">Loading results…</p>
                    </div>
                )}
            </div>
        </MainLayout>
    );
}
