/**
 * Test Taking Page
 * Answer questions with text or voice, then submit
 */

'use client';

import { useEffect, useState, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Mic, MicOff, Loader2 } from 'lucide-react';
import { useCourseStore } from '@/stores/courses';
import { useProgressStore } from '@/stores/progress';
import { useTestsStore, type TestQuestion } from '@/stores/tests';
import { MainLayout } from '@/components/layout';
import { GlassCard, Button } from '@/components/ui';

export default function TakeTestPage() {
    const params = useParams();
    const router = useRouter();
    const courseId = params.courseId as string;
    const testId = params.testId as string;

    const { currentCourse, selectCourse } = useCourseStore();
    const { streak, fetchStreak } = useProgressStore();
    const {
        currentTest,
        lastAttemptId,
        getTest,
        submitAnswers,
        submitVoiceAnswer,
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

    useEffect(() => {
        selectCourse(courseId);
    }, [courseId, selectCourse]);

    useEffect(() => {
        if (courseId) fetchStreak(courseId);
    }, [courseId, fetchStreak]);

    useEffect(() => {
        getTest(testId).catch(() => {});
        return () => clearTest();
    }, [testId]);

    const handleTextChange = (questionId: string, value: string) => {
        setAnswers((prev) => ({ ...prev, [questionId]: value }));
    };

    const startRecording = async (questionId: string) => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const recorder = new MediaRecorder(stream);
            chunksRef.current = [];
            recorder.ondataavailable = (e) => {
                if (e.data.size) chunksRef.current.push(e.data);
            };
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
        const questionIdsWithVoice = Object.keys(voiceBlobs);
        const textAnswers = list
            .filter((q) => !voiceBlobs[q.id] && answers[q.id]?.trim())
            .map((q) => ({ question_id: q.id, answer_text: answers[q.id] }));

        if (textAnswers.length === 0 && questionIdsWithVoice.length === 0) return;

        clearError();
        try {
            let attemptIdResult: string | null = null;

            if (textAnswers.length > 0) {
                attemptIdResult = await submitAnswers(testId, textAnswers);
            }

            for (const qId of questionIdsWithVoice) {
                const file = voiceBlobs[qId];
                if (!file) continue;
                const res = await submitVoiceAnswer(testId, qId, file, attemptIdResult ?? undefined);
                if (!attemptIdResult) attemptIdResult = res;
            }

            const id = attemptIdResult ?? lastAttemptId;
            if (id) router.push(`/courses/${courseId}/tests/${testId}/results?attemptId=${id}`);
        } catch {
            // Error in store
        }
    };

    const hasAnswer = (qId: string) =>
        (answers[qId]?.trim()) || !!voiceBlobs[qId];
    const allAnswered = currentTest?.questions.every((q) => hasAnswer(q.id));

    if (!currentCourse) {
        return (
            <MainLayout>
                <div className="flex items-center justify-center min-h-[60vh]">
                    <p className="text-[var(--text-tertiary)]">Loading...</p>
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
            <div className="max-w-3xl mx-auto px-8 md:px-20 py-12">
                <Link
                    href={`/courses/${courseId}/tests`}
                    className="inline-flex items-center gap-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] mb-8 transition-colors"
                >
                    <ArrowLeft className="w-4 h-4" />
                    Back to tests
                </Link>

                <h1 className="text-2xl font-semibold text-[var(--text-primary)] mb-2">{currentTest.title}</h1>
                <p className="text-sm text-[var(--text-tertiary)] mb-8">
                    {questions.length} questions · Answer with text or record your voice
                </p>

                {error && (
                    <div className="mb-6 px-4 py-3 bg-[var(--error)]/10 border border-[var(--error)]/20 rounded-lg">
                        <p className="text-sm text-[var(--error)]">{error}</p>
                    </div>
                )}

                <div className="space-y-6">
                    {questions.map((q, index) => (
                        <QuestionBlock
                            key={q.id}
                            question={q}
                            index={index + 1}
                            value={answers[q.id] ?? ''}
                            hasVoice={!!voiceBlobs[q.id]}
                            onChange={(value) => handleTextChange(q.id, value)}
                            onStartRecord={() => startRecording(q.id)}
                            onStopRecord={stopRecording}
                            isRecording={recordingQuestionId === q.id}
                        />
                    ))}
                </div>

                <div className="mt-8 flex gap-3">
                    <Button
                        variant="primary"
                        size="lg"
                        disabled={isSubmitting || !allAnswered}
                        onClick={handleSubmit}
                    >
                        {isSubmitting ? (
                            <>
                                <Loader2 className="w-4 h-4 mr-2 inline animate-spin" />
                                Submitting...
                            </>
                        ) : (
                            'Submit test'
                        )}
                    </Button>
                    <Button variant="secondary" onClick={() => router.push(`/courses/${courseId}/tests`)}>
                        Cancel
                    </Button>
                </div>
            </div>
        </MainLayout>
    );
}

function QuestionBlock({
    question,
    index,
    value,
    hasVoice,
    onChange,
    onStartRecord,
    onStopRecord,
    isRecording,
}: {
    question: TestQuestion;
    index: number;
    value: string;
    hasVoice: boolean;
    onChange: (v: string) => void;
    onStartRecord: () => void;
    onStopRecord: () => void;
    isRecording: boolean;
}) {
    return (
        <GlassCard>
            <p className="text-sm font-medium text-[var(--text-tertiary)] mb-2">Question {index}</p>
            <p className="text-[var(--text-primary)] mb-4">{question.question_text}</p>
            {question.answer_options && question.answer_options.length > 0 ? (
                <div className="space-y-2">
                    {question.answer_options.map((opt, i) => (
                        <label key={i} className="flex items-center gap-3 p-2 rounded hover:bg-[var(--bg-sunken)] cursor-pointer">
                            <input
                                type="radio"
                                name={question.id}
                                value={opt}
                                checked={value === opt}
                                onChange={() => onChange(opt)}
                                disabled={hasVoice}
                                className="rounded-full border-[var(--glass-border)]"
                            />
                            <span className="text-sm text-[var(--text-primary)]">{opt}</span>
                        </label>
                    ))}
                </div>
            ) : (
                <>
                    <textarea
                        placeholder="Type your answer..."
                        value={hasVoice ? '' : value}
                        onChange={(e) => onChange(e.target.value)}
                        disabled={hasVoice}
                        rows={4}
                        className="w-full px-4 py-3 bg-[var(--bg-sunken)] border border-[var(--glass-border)] rounded-lg text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)] resize-none"
                    />
                </>
            )}
            {question.question_type !== 'mcq' && (
                <div className="mt-3 flex items-center gap-2 flex-wrap">
                    <button
                        type="button"
                        onClick={isRecording ? onStopRecord : onStartRecord}
                        className={`flex items-center gap-2 text-sm font-medium px-3 py-2 rounded-lg transition-colors ${
                            isRecording
                                ? 'bg-[var(--error)]/20 text-[var(--error)]'
                                : 'bg-[var(--bg-sunken)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                        }`}
                    >
                        {isRecording ? (
                            <>
                                <MicOff className="w-4 h-4" />
                                Stop recording
                            </>
                        ) : (
                            <>
                                <Mic className="w-4 h-4" />
                                {hasVoice ? 'Re-record' : 'Record voice answer'}
                            </>
                        )}
                    </button>
                    {hasVoice && (
                        <span className="text-xs text-[var(--success)]">Voice recorded — submit test when ready</span>
                    )}
                </div>
            )}
        </GlassCard>
    );
}
