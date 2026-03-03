/**
 * Test Generation Page
 * Select topics and generate a practice test
 */

'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Loader2, FileQuestion, ChevronDown, ChevronRight, Minus, Plus } from 'lucide-react';
import { useCourseStore } from '@/stores/courses';
import { useProgressStore } from '@/stores/progress';
import { useTestsStore } from '@/stores/tests';
import { MainLayout } from '@/components/layout';
import { api } from '@/lib/api';

interface TestListItem {
    id: string;
    title: string;
    question_count: number;
    created_at: string;
}

interface AttemptListItem {
    id: string;
    started_at: string;
    completed_at: string | null;
    total_score: number | null;
    max_score: number;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDate(iso: string): string {
    if (!iso) return '—';
    try {
        const d = new Date(iso);
        return (
            d.toLocaleDateString(undefined, { dateStyle: 'short' }) +
            ' ' +
            d.toLocaleTimeString(undefined, { timeStyle: 'short' })
        );
    } catch {
        return iso;
    }
}

function scorePct(score: number | null, max: number): number | null {
    if (score == null || max === 0) return null;
    return Math.round((score / max) * 100);
}

function ScorePill({ score, max }: { score: number | null; max: number }) {
    const pct = scorePct(score, max);
    if (pct == null) return <span className="text-xs text-[var(--text-tertiary)]">No attempts</span>;
    const color =
        pct >= 80 ? 'bg-[#6B8F71]/10 text-[#6B8F71]' :
            pct >= 60 ? 'bg-[#D4A853]/10 text-[#A07830]' :
                'bg-[var(--error)]/10 text-[var(--error)]';
    return (
        <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${color}`}>
            {pct}%
        </span>
    );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function PillToggle({
    options,
    selected,
    onToggle,
}: {
    options: { id: string; label: string }[];
    selected: string[];
    onToggle: (id: string) => void;
}) {
    return (
        <div className="flex flex-wrap gap-2">
            {options.map(({ id, label }) => {
                const active = selected.includes(id);
                return (
                    <button
                        key={id}
                        type="button"
                        onClick={() => onToggle(id)}
                        className={`px-3 py-1.5 rounded-full text-sm font-medium border transition-colors ${active
                            ? 'bg-[var(--text-primary)] text-[var(--bg-elevated)] border-[var(--text-primary)]'
                            : 'bg-[var(--bg-elevated)] text-[var(--text-secondary)] border-[#D6D3D1] hover:border-[var(--text-secondary)]'
                            }`}
                    >
                        {label}
                    </button>
                );
            })}
        </div>
    );
}

function SegmentedControl({
    options,
    value,
    onChange,
}: {
    options: { id: string; label: string }[];
    value: string;
    onChange: (id: string) => void;
}) {
    return (
        <div className="inline-flex rounded-lg border border-[#D6D3D1] overflow-hidden">
            {options.map(({ id, label }) => (
                <button
                    key={id}
                    type="button"
                    onClick={() => onChange(id)}
                    className={`px-4 py-2 text-sm font-medium transition-colors ${value === id
                        ? 'bg-[var(--text-primary)] text-[var(--bg-elevated)]'
                        : 'bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:bg-[var(--bg-sunken)]'
                        }`}
                >
                    {label}
                </button>
            ))}
        </div>
    );
}

function NumberStepper({
    value,
    min,
    max,
    onChange,
}: {
    value: number;
    min: number;
    max: number;
    onChange: (v: number) => void;
}) {
    return (
        <div className="inline-flex items-center rounded-lg border border-[#D6D3D1] overflow-hidden">
            <button
                type="button"
                onClick={() => onChange(Math.max(min, value - 1))}
                className="px-3 py-2 text-[var(--text-secondary)] hover:bg-[var(--bg-sunken)] transition-colors"
            >
                <Minus className="w-4 h-4" />
            </button>
            <span className="w-10 text-center text-sm font-medium text-[var(--text-primary)]">
                {value}
            </span>
            <button
                type="button"
                onClick={() => onChange(Math.min(max, value + 1))}
                className="px-3 py-2 text-[var(--text-secondary)] hover:bg-[var(--bg-sunken)] transition-colors"
            >
                <Plus className="w-4 h-4" />
            </button>
        </div>
    );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function TestsPage() {
    const params = useParams();
    const router = useRouter();
    const courseId = params.courseId as string;

    const { currentCourse, selectCourse } = useCourseStore();
    const { streak, fetchStreak } = useProgressStore();
    const { generateTest, isGenerating, error, clearError } = useTestsStore();

    const [testList, setTestList] = useState<TestListItem[]>([]);
    const [attemptsByTest, setAttemptsByTest] = useState<Record<string, AttemptListItem[]>>({});
    const [expandedTestId, setExpandedTestId] = useState<string | null>(null);
    const [selectedTopicIds, setSelectedTopicIds] = useState<string[]>([]);
    const [questionCount, setQuestionCount] = useState(10);
    const [difficulty, setDifficulty] = useState<'easy' | 'medium' | 'hard'>('medium');
    const [questionTypes, setQuestionTypes] = useState<string[]>(['mcq', 'short_answer']);
    const isFetchingTestsRef = useRef(false);

    useEffect(() => { selectCourse(courseId); }, [courseId, selectCourse]);
    useEffect(() => { if (courseId) fetchStreak(courseId); }, [courseId, fetchStreak]);
    useEffect(() => {
        if (!courseId || isFetchingTestsRef.current) return;
        isFetchingTestsRef.current = true;
        api.ai.listTests(courseId)
            .then((res) => setTestList(res.data || []))
            .catch(() => setTestList([]))
            .finally(() => { isFetchingTestsRef.current = false; });
    }, [courseId]);

    const loadAttempts = async (testId: string) => {
        if (attemptsByTest[testId]) return;
        try {
            const res = await api.ai.listAttempts(testId);
            setAttemptsByTest((prev) => ({ ...prev, [testId]: res.data || [] }));
        } catch {
            setAttemptsByTest((prev) => ({ ...prev, [testId]: [] }));
        }
    };

    const toggleAttempts = (testId: string) => {
        if (expandedTestId === testId) {
            setExpandedTestId(null);
        } else {
            setExpandedTestId(testId);
            loadAttempts(testId);
        }
    };

    const topics = currentCourse?.topics ?? [];

    const toggleTopic = (id: string) =>
        setSelectedTopicIds((prev) =>
            prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]
        );

    const toggleType = (id: string) =>
        setQuestionTypes((prev) =>
            prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]
        );

    const handleGenerate = async () => {
        if (selectedTopicIds.length === 0 || questionTypes.length === 0) return;
        clearError();
        try {
            const test = await generateTest(courseId, selectedTopicIds, questionCount, difficulty, questionTypes);
            router.push(`/courses/${courseId}/tests/${test.id}`);
        } catch {
            // Error set in store
        }
    };

    if (!currentCourse) {
        return (
            <MainLayout>
                <div className="flex items-center justify-center min-h-[60vh]">
                    <Loader2 className="w-6 h-6 animate-spin text-[var(--text-tertiary)]" />
                </div>
            </MainLayout>
        );
    }

    const typeOptions = [
        { id: 'mcq', label: 'Multiple choice' },
        { id: 'short_answer', label: 'Short answer' },
        { id: 'essay', label: 'Essay' },
    ];

    const difficultyOptions = [
        { id: 'easy', label: 'Easy' },
        { id: 'medium', label: 'Medium' },
        { id: 'hard', label: 'Hard' },
    ];

    return (
        <MainLayout
            currentCourse={{ id: currentCourse.id, code: currentCourse.code, name: currentCourse.name }}
            streak={streak}
        >
            <div className="max-w-2xl mx-auto px-8 md:px-20 py-12">
                <Link
                    href={`/courses/${courseId}`}
                    className="inline-flex items-center gap-2 text-sm text-[var(--text-tertiary)] hover:text-[var(--text-primary)] mb-8 transition-colors"
                >
                    <ArrowLeft className="w-4 h-4" />
                    Back to {currentCourse.code}
                </Link>

                <h1 className="text-2xl font-semibold text-[var(--text-primary)] mb-1">Practice Test</h1>
                <p className="text-sm text-[var(--text-tertiary)] mb-8">
                    Select topics and configure your quiz below.
                </p>

                {/* Error */}
                {error && (
                    <div className="mb-6 px-4 py-3 rounded-lg bg-[var(--error)]/10 border border-[var(--error)]/20">
                        <p className="text-sm text-[var(--error)]">{error}</p>
                    </div>
                )}

                {/* ── Existing tests ─────────────────────────────── */}
                {testList.length > 0 && (
                    <section className="mb-10">
                        <h2 className="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wider mb-3">
                            Your tests
                        </h2>
                        <div className="border border-[var(--glass-border)] rounded-xl overflow-hidden divide-y divide-[var(--glass-border)]">
                            {testList.map((test) => {
                                const attempts = attemptsByTest[test.id] ?? [];
                                const bestScore = attempts.reduce(
                                    (best, a) =>
                                        a.total_score != null && (best == null || a.total_score > best)
                                            ? a.total_score
                                            : best,
                                    null as number | null
                                );
                                const maxScore = attempts[0]?.max_score ?? 0;
                                return (
                                    <div key={test.id} className="bg-[var(--bg-elevated)]">
                                        <div className="flex items-center gap-3 px-4 py-3">
                                            <div className="w-8 h-8 rounded-lg bg-[var(--bg-sunken)] flex items-center justify-center shrink-0">
                                                <FileQuestion className="w-4 h-4 text-[var(--text-tertiary)]" />
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <p className="text-sm font-medium text-[var(--text-primary)] truncate">{test.title}</p>
                                                <p className="text-xs text-[var(--text-tertiary)]">
                                                    {test.question_count} questions · {formatDate(test.created_at)}
                                                </p>
                                            </div>
                                            <div className="flex items-center gap-2 shrink-0">
                                                {attempts.length > 0 && (
                                                    <ScorePill score={bestScore} max={maxScore} />
                                                )}
                                                <button
                                                    onClick={() => router.push(`/courses/${courseId}/tests/${test.id}`)}
                                                    className="px-3 py-1.5 rounded-lg bg-[var(--accent-primary)] text-[var(--bg-elevated)] text-xs font-medium hover:bg-[var(--accent-hover)] transition-colors"
                                                >
                                                    Take test
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => toggleAttempts(test.id)}
                                                    className="flex items-center gap-1 text-xs text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors px-1"
                                                >
                                                    {expandedTestId === test.id
                                                        ? <ChevronDown className="w-4 h-4" />
                                                        : <ChevronRight className="w-4 h-4" />}
                                                    History
                                                </button>
                                            </div>
                                        </div>

                                        {expandedTestId === test.id && (
                                            <div className="bg-[var(--bg-sunken)] border-t border-[var(--glass-border)] px-4 py-3">
                                                {!attemptsByTest[test.id] ? (
                                                    <p className="text-xs text-[var(--text-tertiary)] flex items-center gap-2">
                                                        <Loader2 className="w-3 h-3 animate-spin" />
                                                        Loading attempts…
                                                    </p>
                                                ) : attempts.length === 0 ? (
                                                    <p className="text-xs text-[var(--text-tertiary)]">No attempts yet.</p>
                                                ) : (
                                                    <div className="space-y-1">
                                                        {attempts.map((a) => {
                                                            const pct = scorePct(a.total_score, a.max_score);
                                                            return (
                                                                <div key={a.id} className="flex items-center justify-between text-xs">
                                                                    <span className="text-[var(--text-secondary)]">{formatDate(a.started_at)}</span>
                                                                    <div className="flex items-center gap-3">
                                                                        {pct != null && (
                                                                            <span className="text-[var(--text-primary)] font-medium">
                                                                                {a.total_score!.toFixed(0)} / {a.max_score} ({pct}%)
                                                                            </span>
                                                                        )}
                                                                        <Link
                                                                            href={`/courses/${courseId}/tests/${test.id}/results?attemptId=${a.id}`}
                                                                            className="text-[var(--accent-primary)] font-medium hover:underline"
                                                                        >
                                                                            View results →
                                                                        </Link>
                                                                    </div>
                                                                </div>
                                                            );
                                                        })}
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    </section>
                )}

                {/* ── Generate new test ────────────────────────────── */}
                <h2 className="text-xs font-semibold text-[var(--text-tertiary)] uppercase tracking-wider mb-3">
                    Generate new test
                </h2>

                <div className="space-y-4">
                    {/* Topics */}
                    <div className="border border-[var(--glass-border)] rounded-xl bg-[var(--bg-elevated)] p-5">
                        <div className="flex items-center justify-between mb-3">
                            <h3 className="text-sm font-medium text-[var(--text-primary)]">Topics</h3>
                            {topics.length > 0 && (
                                <div className="flex gap-3 text-xs">
                                    <button
                                        type="button"
                                        onClick={() => setSelectedTopicIds(topics.map((t) => t.id))}
                                        className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors"
                                    >
                                        Select all
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => setSelectedTopicIds([])}
                                        className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors"
                                    >
                                        Clear
                                    </button>
                                </div>
                            )}
                        </div>
                        {topics.length === 0 ? (
                            <p className="text-sm text-[var(--text-tertiary)]">No topics in this course yet.</p>
                        ) : (
                            <PillToggle
                                options={topics.map((t) => ({ id: t.id, label: t.title }))}
                                selected={selectedTopicIds}
                                onToggle={toggleTopic}
                            />
                        )}
                    </div>

                    {/* Options */}
                    <div className="border border-[var(--glass-border)] rounded-xl bg-[var(--bg-elevated)] p-5 space-y-5">
                        <h3 className="text-sm font-medium text-[var(--text-primary)]">Options</h3>

                        {/* Question count */}
                        <div className="flex items-center justify-between">
                            <span className="text-sm text-[var(--text-secondary)]">Number of questions</span>
                            <NumberStepper value={questionCount} min={0} max={30} onChange={setQuestionCount} />
                        </div>

                        {/* Difficulty */}
                        <div className="flex items-center justify-between flex-wrap gap-3">
                            <span className="text-sm text-[var(--text-secondary)]">Difficulty</span>
                            <SegmentedControl
                                options={difficultyOptions}
                                value={difficulty}
                                onChange={(v) => setDifficulty(v as 'easy' | 'medium' | 'hard')}
                            />
                        </div>

                        {/* Question types */}
                        <div>
                            <p className="text-sm text-[var(--text-secondary)] mb-2.5">Question types</p>
                            <PillToggle
                                options={typeOptions}
                                selected={questionTypes}
                                onToggle={toggleType}
                            />
                            {questionTypes.length === 0 && (
                                <p className="text-xs text-[var(--error)] mt-1.5">Select at least one type</p>
                            )}
                        </div>
                    </div>

                    {/* Generate button */}
                    <button
                        onClick={handleGenerate}
                        disabled={isGenerating || selectedTopicIds.length === 0 || questionTypes.length === 0}
                        className="w-full py-3 rounded-xl bg-[var(--accent-primary)] text-[var(--bg-elevated)] text-sm font-medium
                                   hover:bg-[var(--accent-hover)] active:scale-[0.99] transition-all
                                   disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                        {isGenerating ? (
                            <>
                                <Loader2 className="w-4 h-4 animate-spin" />
                                Generating test…
                            </>
                        ) : (
                            'Generate Test'
                        )}
                    </button>
                </div>
            </div>
        </MainLayout>
    );
}
