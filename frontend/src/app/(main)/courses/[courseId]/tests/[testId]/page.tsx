/**
 * Test Taking Page
 * Answer questions with text or voice, then submit
 */

'use client';

import { useEffect, useState, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Mic, MicOff, Loader2, CheckCircle2 } from 'lucide-react';
import { useCourseStore } from '@/stores/courses';
import { useProgressStore } from '@/stores/progress';
import { useTestsStore, type TestQuestion } from '@/stores/tests';
import { MainLayout } from '@/components/layout';

export default function TakeTestPage() {
    const params = useParams();
    const router = useRouter();
    const courseId = params.courseId as string;
    const testId = params.testId as string;

    const { currentCourse, selectCourse } = useCourseStore();
    const { streak, fetchStreak } = useProgressStore();
    const {
        currentTest,
        getTest,
        submitFull,
        isSubmitting,
        error,
        clearTest,
        clearError,
    } = useTestsStore();

    const [answers, setAnswers] = useState<Record<string, string>>({});
    const [voiceBlobs, setVoiceBlobs] = useState<Record<string, File>>({});
    const [recordingQuestionId, setRecordingQuestionId] = useState<string | null>(null);
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const chunksRef = useRef<Blob[]>([]);

    useEffect(() => { selectCourse(courseId); }, [courseId, selectCourse]);
    useEffect(() => { if (courseId) fetchStreak(courseId); }, [courseId, fetchStreak]);
    useEffect(() => {
        getTest(testId).catch(() => { });
        return () => clearTest();
    }, [testId]);

    const handleTextChange = (questionId: string, value: string) =>
        setAnswers((prev) => ({ ...prev, [questionId]: value }));

    const startRecording = async (questionId: string) => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const recorder = new MediaRecorder(stream);
            chunksRef.current = [];
            recorder.ondataavailable = (e) => { if (e.data.size) chunksRef.current.push(e.data); };
            recorder.onstop = () => {
                stream.getTracks().forEach((t) => t.stop());
                const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
                const file = new File([blob], 'voice.webm', { type: 'audio/webm' });
                setVoiceBlobs((prev) => ({ ...prev, [questionId]: file }));
                setRecordingQuestionId(null);
            };
            recorder.start();
            mediaRecorderRef.current = recorder;
            setRecordingQuestionId(questionId);
        } catch (err) {
            console.error('Microphone access failed:', err);
            setRecordingQuestionId(null);
        }
    };

    const stopRecording = () => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
            mediaRecorderRef.current.stop();
        }
    };

    const handleSubmit = async () => {
        const list = currentTest?.questions ?? [];
        const allAnswers = list
            .filter((q) => voiceBlobs[q.id] || answers[q.id]?.trim())
            .map((q) => ({
                question_id: q.id,
                answer_text: voiceBlobs[q.id] ? '' : (answers[q.id] ?? ''),
                is_voice: !!voiceBlobs[q.id],
            }));
        if (allAnswers.length === 0) return;
        clearError();
        try {
            const attemptId = await submitFull(testId, allAnswers, voiceBlobs);
            router.push(`/courses/${courseId}/tests/${testId}/results?attemptId=${attemptId}`);
        } catch {
            // Error handled in store
        }
    };

    const hasAnswer = (qId: string) => !!(answers[qId]?.trim()) || !!voiceBlobs[qId];
    const answeredCount = currentTest?.questions.filter((q) => hasAnswer(q.id)).length ?? 0;
    const totalCount = currentTest?.questions.length ?? 0;
    const allAnswered = answeredCount === totalCount && totalCount > 0;
    const progressPct = totalCount > 0 ? (answeredCount / totalCount) * 100 : 0;

    if (!currentCourse) {
        return (
            <MainLayout>
                <div className="flex items-center justify-center min-h-[60vh]">
                    <Loader2 className="w-6 h-6 animate-spin text-[var(--text-tertiary)]" />
                </div>
            </MainLayout>
        );
    }

    if (!currentTest) {
        return (
            <MainLayout
                currentCourse={{ id: currentCourse.id, code: currentCourse.code, name: currentCourse.name }}
                streak={streak}
            >
                <div className="max-w-3xl mx-auto px-8 md:px-20 py-12">
                    <div className="flex items-center justify-center min-h-[40vh]">
                        <Loader2 className="w-8 h-8 animate-spin text-[var(--text-tertiary)]" />
                    </div>
                </div>
            </MainLayout>
        );
    }

    const questions = currentTest.questions;

    return (
        <MainLayout
            currentCourse={{ id: currentCourse.id, code: currentCourse.code, name: currentCourse.name }}
            streak={streak}
        >
            {/* Progress bar */}
            <div className="fixed top-16 left-0 right-0 z-20 h-1 bg-[var(--bg-sunken)]">
                <div
                    className="h-full bg-[var(--accent-primary)] transition-all duration-300"
                    style={{ width: `${progressPct}%` }}
                />
            </div>

            <div className="max-w-3xl mx-auto px-8 md:px-20 pt-10 pb-28">
                <Link
                    href={`/courses/${courseId}/tests`}
                    className="inline-flex items-center gap-2 text-sm text-[var(--text-tertiary)] hover:text-[var(--text-primary)] mb-8 transition-colors"
                >
                    <ArrowLeft className="w-4 h-4" />
                    Back to tests
                </Link>

                <h1 className="text-2xl font-semibold text-[var(--text-primary)] mb-1">{currentTest.title}</h1>
                <p className="text-sm text-[var(--text-tertiary)] mb-8">
                    {answeredCount} / {questions.length} answered
                </p>

                {error && (
                    <div className="mb-6 px-4 py-3 rounded-lg bg-[var(--error)]/10 border border-[var(--error)]/20">
                        <p className="text-sm text-[var(--error)]">{error}</p>
                    </div>
                )}

                <div className="space-y-5">
                    {questions.map((q, index) => (
                        <QuestionBlock
                            key={q.id}
                            question={q}
                            index={index + 1}
                            value={answers[q.id] ?? ''}
                            hasVoice={!!voiceBlobs[q.id]}
                            isAnswered={hasAnswer(q.id)}
                            onChange={(value) => handleTextChange(q.id, value)}
                            onStartRecord={() => startRecording(q.id)}
                            onStopRecord={stopRecording}
                            isRecording={recordingQuestionId === q.id}
                        />
                    ))}
                </div>
            </div>

            {/* Sticky submit bar */}
            <div className="fixed bottom-0 left-0 right-0 z-20 bg-[var(--bg-elevated)] border-t border-[var(--glass-border)]">
                <div className="max-w-3xl mx-auto px-8 md:px-20 py-4 flex items-center justify-between gap-4">
                    <div className="text-sm text-[var(--text-secondary)]">
                        <span className="font-medium text-[var(--text-primary)]">{answeredCount}</span> / {totalCount} questions answered
                        {!allAnswered && <span className="ml-2 text-[var(--text-tertiary)]">(answer all to submit)</span>}
                    </div>
                    <div className="flex gap-3">
                        <button
                            onClick={() => router.push(`/courses/${courseId}/tests`)}
                            className="px-4 py-2 rounded-lg text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-sunken)] transition-colors"
                        >
                            Cancel
                        </button>
                        <button
                            disabled={isSubmitting || !allAnswered}
                            onClick={handleSubmit}
                            className="px-5 py-2 rounded-lg bg-[var(--accent-primary)] text-[var(--bg-elevated)] text-sm font-medium
                                       hover:bg-[var(--accent-hover)] transition-colors disabled:opacity-40 disabled:cursor-not-allowed
                                       flex items-center gap-2"
                        >
                            {isSubmitting ? (
                                <>
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                    Submitting…
                                </>
                            ) : (
                                'Submit test'
                            )}
                        </button>
                    </div>
                </div>
            </div>
        </MainLayout>
    );
}

// ── QuestionBlock ─────────────────────────────────────────────────────────────

function QuestionBlock({
    question,
    index,
    value,
    hasVoice,
    isAnswered,
    onChange,
    onStartRecord,
    onStopRecord,
    isRecording,
}: {
    question: TestQuestion;
    index: number;
    value: string;
    hasVoice: boolean;
    isAnswered: boolean;
    onChange: (v: string) => void;
    onStartRecord: () => void;
    onStopRecord: () => void;
    isRecording: boolean;
}) {
    return (
        <div className={`rounded-xl border bg-[var(--bg-elevated)] transition-colors ${isAnswered ? 'border-[#A09088]' : 'border-[var(--glass-border)]'
            }`}>
            {/* Question header */}
            <div className="flex items-start gap-4 p-5 pb-4">
                <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold shrink-0 mt-0.5 transition-colors ${isAnswered
                        ? 'bg-[var(--accent-primary)] text-[var(--bg-elevated)]'
                        : 'bg-[var(--bg-sunken)] text-[var(--text-tertiary)]'
                    }`}>
                    {isAnswered ? <CheckCircle2 className="w-4 h-4" /> : index}
                </div>
                <p className="text-sm font-medium text-[var(--text-primary)] leading-relaxed flex-1">
                    {question.question_text}
                </p>
            </div>

            {/* Answer area */}
            <div className="px-5 pb-5">
                {question.answer_options && question.answer_options.length > 0 ? (
                    /* MCQ options — custom styled */
                    <div className="space-y-2 ml-11">
                        {question.answer_options.map((opt, i) => {
                            const selected = value === opt;
                            return (
                                <label
                                    key={i}
                                    className={`flex items-center gap-3 px-4 py-3 rounded-lg border cursor-pointer transition-colors ${selected
                                            ? 'border-[var(--accent-primary)] bg-[var(--accent-primary)] text-[var(--bg-elevated)]'
                                            : 'border-[var(--glass-border)] bg-[var(--bg-sunken)] text-[var(--text-secondary)] hover:border-[#A09088]'
                                        }`}
                                >
                                    <div className={`w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 ${selected
                                            ? 'border-[var(--bg-elevated)]'
                                            : 'border-[#C4BAB0]'
                                        }`}>
                                        {selected && <div className="w-2 h-2 rounded-full bg-[var(--bg-elevated)]" />}
                                    </div>
                                    <input
                                        type="radio"
                                        name={question.id}
                                        value={opt}
                                        checked={selected}
                                        onChange={() => onChange(opt)}
                                        disabled={hasVoice}
                                        className="sr-only"
                                    />
                                    <span className="text-sm">{opt}</span>
                                </label>
                            );
                        })}
                    </div>
                ) : (
                    /* Text / essay */
                    <div className="ml-11">
                        <textarea
                            placeholder="Type your answer…"
                            value={hasVoice ? '' : value}
                            onChange={(e) => onChange(e.target.value)}
                            disabled={hasVoice}
                            rows={4}
                            className="w-full px-4 py-3 bg-[var(--bg-sunken)] border border-[var(--glass-border)] rounded-lg
                                       text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)]
                                       focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)] resize-none
                                       disabled:opacity-50"
                        />
                    </div>
                )}

                {/* Voice recording (not for MCQ) */}
                {question.question_type !== 'mcq' && (
                    <div className="mt-3 flex items-center gap-3 ml-11">
                        <button
                            type="button"
                            onClick={isRecording ? onStopRecord : onStartRecord}
                            className={`flex items-center gap-2 text-sm px-3 py-2 rounded-lg font-medium transition-colors ${isRecording
                                    ? 'bg-[var(--error)]/10 text-[var(--error)] border border-[var(--error)]/20'
                                    : 'bg-[var(--bg-sunken)] text-[var(--text-secondary)] hover:bg-[var(--bg-sunken)]'
                                }`}
                        >
                            {isRecording ? (
                                <>
                                    <span className="w-2 h-2 rounded-full bg-[var(--error)] animate-pulse" />
                                    <MicOff className="w-3.5 h-3.5" />
                                    Stop recording
                                </>
                            ) : (
                                <>
                                    <Mic className="w-3.5 h-3.5" />
                                    {hasVoice ? 'Re-record' : 'Record voice'}
                                </>
                            )}
                        </button>
                        {hasVoice && !isRecording && (
                            <span className="text-xs text-[var(--success)] font-medium">
                                ✓ Voice recorded
                            </span>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
}
