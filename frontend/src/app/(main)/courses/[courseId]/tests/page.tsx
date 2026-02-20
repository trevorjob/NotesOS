/**
 * Test Generation Page
 * Select topics and generate a practice test
 */

'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Loader2, FileQuestion, ChevronDown, ChevronRight } from 'lucide-react';
import { useCourseStore } from '@/stores/courses';
import { useProgressStore } from '@/stores/progress';
import { useTestsStore } from '@/stores/tests';
import { MainLayout } from '@/components/layout';
import { GlassCard, Button, Input } from '@/components/ui';
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

    useEffect(() => {
        selectCourse(courseId);
    }, [courseId, selectCourse]);

    useEffect(() => {
        if (courseId) fetchStreak(courseId);
    }, [courseId, fetchStreak]);

    useEffect(() => {
        if (!courseId) return;
        api.ai.listTests(courseId)
            .then((res) => setTestList(res.data || []))
            .catch(() => setTestList([]));
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

    const formatDate = (iso: string) => {
        if (!iso) return '—';
        try {
            const d = new Date(iso);
            return d.toLocaleDateString(undefined, { dateStyle: 'short' }) + ' ' + d.toLocaleTimeString(undefined, { timeStyle: 'short' });
        } catch {
            return iso;
        }
    };

    const topics = currentCourse?.topics ?? [];

    const toggleTopic = (topicId: string) => {
        setSelectedTopicIds((prev) =>
            prev.includes(topicId) ? prev.filter((id) => id !== topicId) : [...prev, topicId]
        );
    };

    const toggleQuestionType = (type: string) => {
        setQuestionTypes((prev) =>
            prev.includes(type) ? prev.filter((t) => t !== type) : [...prev, type]
        );
    };

    const handleGenerate = async () => {
        if (selectedTopicIds.length === 0) return;
        if (questionTypes.length === 0) return;
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
            <div className="max-w-2xl mx-auto px-8 md:px-20 py-12">
                <Link
                    href={`/courses/${courseId}`}
                    className="inline-flex items-center gap-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] mb-8 transition-colors"
                >
                    <ArrowLeft className="w-4 h-4" />
                    Back to {currentCourse.code}
                </Link>

                <h1 className="text-2xl font-semibold text-[var(--text-primary)] mb-2">Practice Test</h1>
                <p className="text-sm text-[var(--text-tertiary)] mb-8">
                    Select topics and generate a quiz. You can answer with text or voice.
                </p>

                {error && (
                    <div className="mb-6 px-4 py-3 bg-[var(--error)]/10 border border-[var(--error)]/20 rounded-lg">
                        <p className="text-sm text-[var(--error)]">{error}</p>
                    </div>
                )}

                {testList.length > 0 && (
                    <GlassCard className="mb-6">
                        <h2 className="text-lg font-medium text-[var(--text-primary)] mb-4">Your generated tests</h2>
                        <div className="space-y-3">
                            {testList.map((test) => (
                                <div key={test.id} className="border border-[var(--glass-border)] rounded-lg p-4">
                                    <div className="flex items-center justify-between flex-wrap gap-2">
                                        <div className="flex items-center gap-2">
                                            <FileQuestion className="w-5 h-5 text-[var(--text-tertiary)]" />
                                            <div>
                                                <p className="font-medium text-[var(--text-primary)]">{test.title}</p>
                                                <p className="text-xs text-[var(--text-tertiary)]">
                                                    {test.question_count} questions · {formatDate(test.created_at)}
                                                </p>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <Button variant="primary" size="sm" onClick={() => router.push(`/courses/${courseId}/tests/${test.id}`)}>
                                                Take test
                                            </Button>
                                            <button
                                                type="button"
                                                onClick={() => toggleAttempts(test.id)}
                                                className="flex items-center gap-1 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                                            >
                                                {expandedTestId === test.id ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                                                Attempts
                                            </button>
                                        </div>
                                    </div>
                                    {expandedTestId === test.id && (
                                        <div className="mt-4 pt-4 border-t border-[var(--glass-border)]">
                                            {!attemptsByTest[test.id] ? (
                                                <p className="text-sm text-[var(--text-tertiary)]">Loading attempts...</p>
                                            ) : attemptsByTest[test.id].length === 0 ? (
                                                <p className="text-sm text-[var(--text-tertiary)]">No attempts yet.</p>
                                            ) : (
                                                <ul className="space-y-2">
                                                    {attemptsByTest[test.id].map((a) => (
                                                        <li key={a.id} className="flex items-center justify-between text-sm">
                                                            <span className="text-[var(--text-secondary)]">
                                                                {formatDate(a.started_at)}
                                                                {a.total_score != null && a.max_score ? ` · ${a.total_score.toFixed(0)} / ${a.max_score}` : ''}
                                                            </span>
                                                            <Link
                                                                href={`/courses/${courseId}/tests/${test.id}/results?attemptId=${a.id}`}
                                                                className="text-[var(--accent-primary)] hover:underline"
                                                            >
                                                                View results
                                                            </Link>
                                                        </li>
                                                    ))}
                                                </ul>
                                            )}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    </GlassCard>
                )}

                <h2 className="text-lg font-medium text-[var(--text-primary)] mb-3">Generate new test</h2>
                <GlassCard className="mb-6">
                    <h3 className="text-base font-medium text-[var(--text-primary)] mb-4">Topics</h3>
                    {topics.length === 0 ? (
                        <p className="text-sm text-[var(--text-tertiary)]">No topics in this course yet.</p>
                    ) : (
                        <div className="space-y-2">
                            {topics.map((topic) => (
                                <label
                                    key={topic.id}
                                    className="flex items-center gap-3 p-3 rounded-lg hover:bg-[var(--bg-sunken)] cursor-pointer transition-colors"
                                >
                                    <input
                                        type="checkbox"
                                        checked={selectedTopicIds.includes(topic.id)}
                                        onChange={() => toggleTopic(topic.id)}
                                        className="rounded border-[var(--glass-border)]"
                                    />
                                    <span className="text-sm text-[var(--text-primary)]">{topic.title}</span>
                                </label>
                            ))}
                        </div>
                    )}
                </GlassCard>

                <GlassCard className="mb-6">
                    <h3 className="text-base font-medium text-[var(--text-primary)] mb-4">Options</h3>
                    <div className="space-y-4">
                        <Input
                            label="Number of questions"
                            type="number"
                            min={1}
                            max={30}
                            value={questionCount}
                            onChange={(e) => setQuestionCount(Number(e.target.value) || 10)}
                        />
                        <div>
                            <label className="block text-sm font-medium text-[var(--text-primary)] mb-2">
                                Difficulty
                            </label>
                            <select
                                value={difficulty}
                                onChange={(e) => setDifficulty(e.target.value as 'easy' | 'medium' | 'hard')}
                                className="w-full px-4 py-2.5 bg-[var(--bg-sunken)] border border-[var(--glass-border)] rounded-lg text-sm text-[var(--text-primary)]"
                            >
                                <option value="easy">Easy</option>
                                <option value="medium">Medium</option>
                                <option value="hard">Hard</option>
                            </select>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-[var(--text-primary)] mb-2">
                                Question types
                            </label>
                            <div className="flex flex-wrap gap-4">
                                {[
                                    { id: 'mcq', label: 'Multiple choice' },
                                    { id: 'short_answer', label: 'Short answer' },
                                    { id: 'essay', label: 'Essay' },
                                ].map(({ id, label }) => (
                                    <label key={id} className="flex items-center gap-2 cursor-pointer">
                                        <input
                                            type="checkbox"
                                            checked={questionTypes.includes(id)}
                                            onChange={() => toggleQuestionType(id)}
                                            className="rounded border-[var(--glass-border)]"
                                        />
                                        <span className="text-sm text-[var(--text-primary)]">{label}</span>
                                    </label>
                                ))}
                            </div>
                            <p className="text-xs text-[var(--text-tertiary)] mt-1">Select at least one</p>
                        </div>
                    </div>
                </GlassCard>

                <Button
                    variant="primary"
                    size="lg"
                    className="w-full"
                    disabled={isGenerating || selectedTopicIds.length === 0 || questionTypes.length === 0}
                    onClick={handleGenerate}
                >
                    {isGenerating ? (
                        <>
                            <Loader2 className="w-4 h-4 mr-2 inline animate-spin" />
                            Generating...
                        </>
                    ) : (
                        'Generate Test'
                    )}
                </Button>
            </div>
        </MainLayout>
    );
}
