/**
 * NotesOS - Join Course Page
 * Form to join an existing course
 */

'use client';

import { useState, FormEvent, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, CheckCircle } from 'lucide-react';
import { useCourseStore } from '@/stores/courses';
import { MainLayout } from '@/components/layout';
import { GlassCard, PageHeader, Input, Button } from '@/components/ui';
import { api } from '@/lib/api';

export default function JoinCoursePage() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const { joinCourse, error, clearError } = useCourseStore();

    const [joinMode, setJoinMode] = useState<'course' | 'class'>('course');
    const [identifier, setIdentifier] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [joinResult, setJoinResult] = useState<{ courses_joined: string[]; owner_name: string; class_name?: string } | null>(null);

    useEffect(() => {
        const classCode = searchParams.get('class');
        if (classCode) {
            setJoinMode('class');
            setIdentifier(classCode);
        }
    }, [searchParams]);

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        clearError();
        setIsSubmitting(true);
        setJoinResult(null);

        try {
            if (joinMode === 'class') {
                const response = await api.invites.joinClass(identifier.toUpperCase());
                setJoinResult({
                    courses_joined: response.data.courses_joined || [],
                    owner_name: response.data.owner_name,
                    class_name: response.data.class_name || undefined,
                });
                // Refresh courses list
                await useCourseStore.getState().fetchCourses();
            } else {
                await joinCourse(identifier);
                router.push('/courses');
            }
        } catch (err: any) {
            console.error('Failed to join:', err);
            setError(err.response?.data?.detail || 'Failed to join');
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <MainLayout>
            <div className="max-w-2xl mx-auto px-8 md:px-20 py-12">
                <Link
                    href="/courses"
                    className="inline-flex items-center gap-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors mb-8"
                >
                    <ArrowLeft className="w-4 h-4" />
                    Back to courses
                </Link>

                <PageHeader
                    title={joinMode === 'class' ? 'Join by Class Code' : 'Join a Course'}
                    subtitle={joinMode === 'class' ? 'Enter a class invite code to join all courses' : 'Enter a course code or invite link to join'}
                />

                <GlassCard>
                    {error && (
                        <div className="mb-6 px-4 py-3 bg-[var(--error)]/10 border border-[var(--error)]/20 rounded-lg">
                            <p className="text-sm text-[var(--error)]">{error}</p>
                        </div>
                    )}

                    {joinResult ? (
                        <div className="space-y-4">
                            <div className="flex items-center gap-2 text-[var(--success)] mb-4">
                                <CheckCircle className="w-5 h-5" />
                                <p className="font-medium">Successfully joined!</p>
                            </div>
                            <div className="bg-[var(--bg-sunken)] p-4 rounded-lg">
                                <p className="text-sm text-[var(--text-primary)] mb-2">
                                    <strong>{joinResult.class_name || 'Class'}</strong> by {joinResult.owner_name}
                                </p>
                                <p className="text-sm text-[var(--text-secondary)] mb-3">
                                    You've been enrolled in {joinResult.courses_joined.length} {joinResult.courses_joined.length === 1 ? 'course' : 'courses'}:
                                </p>
                                <ul className="text-sm text-[var(--text-tertiary)] space-y-1 list-disc list-inside">
                                    {joinResult.courses_joined.map((course, i) => (
                                        <li key={i}>{course}</li>
                                    ))}
                                </ul>
                            </div>
                            <Button variant="primary" onClick={() => router.push('/courses')} className="w-full">
                                Go to courses
                            </Button>
                        </div>
                    ) : (
                        <>
                            <div className="flex gap-2 mb-6">
                                <button
                                    type="button"
                                    onClick={() => {
                                        setJoinMode('course');
                                        setIdentifier('');
                                        clearError();
                                    }}
                                    className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                                        joinMode === 'course'
                                            ? 'bg-[var(--accent-primary)] text-white'
                                            : 'bg-[var(--bg-sunken)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                                    }`}
                                >
                                    Course Code
                                </button>
                                <button
                                    type="button"
                                    onClick={() => {
                                        setJoinMode('class');
                                        setIdentifier('');
                                        clearError();
                                    }}
                                    className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                                        joinMode === 'class'
                                            ? 'bg-[var(--accent-primary)] text-white'
                                            : 'bg-[var(--bg-sunken)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                                    }`}
                                >
                                    Class Code
                                </button>
                            </div>

                            <form onSubmit={handleSubmit} className="space-y-5">
                                <Input
                                    label={joinMode === 'class' ? 'Class Invite Code' : 'Course Code or Invite Link'}
                                    type="text"
                                    placeholder={joinMode === 'class' ? 'ABC123' : 'HIST 101 or course-invite-code'}
                                    value={identifier}
                                    onChange={(e) => setIdentifier(e.target.value)}
                                    required
                                />

                                <div className="bg-[var(--bg-sunken)] p-4 rounded-lg">
                                    <p className="text-sm text-[var(--text-secondary)] mb-2">
                                        <strong>How to join:</strong>
                                    </p>
                                    {joinMode === 'class' ? (
                                        <ul className="text-sm text-[var(--text-tertiary)] space-y-1 list-disc list-inside">
                                            <li>Enter the class invite code from your instructor</li>
                                            <li>You'll be enrolled in all courses the instructor is enrolled in</li>
                                        </ul>
                                    ) : (
                                        <ul className="text-sm text-[var(--text-tertiary)] space-y-1 list-disc list-inside">
                                            <li>Enter the course code (e.g., HIST 101)</li>
                                            <li>Or paste an invite link from your instructor</li>
                                        </ul>
                                    )}
                                </div>

                                <div className="flex gap-3 pt-4">
                                    <Button
                                        type="button"
                                        variant="secondary"
                                        onClick={() => router.back()}
                                        disabled={isSubmitting}
                                    >
                                        Cancel
                                    </Button>
                                    <Button
                                        type="submit"
                                        variant="primary"
                                        className="flex-1"
                                        disabled={isSubmitting}
                                    >
                                        {isSubmitting ? 'Joining...' : joinMode === 'class' ? 'Join Class' : 'Join Course'}
                                    </Button>
                                </div>
                            </form>
                        </>
                    )}
                </GlassCard>
            </div>
        </MainLayout>
    );
}
