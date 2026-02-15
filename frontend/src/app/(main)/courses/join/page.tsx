/**
 * NotesOS - Join Course Page
 * Form to join an existing course
 */

'use client';

import { useState, FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { useCourseStore } from '@/stores/courses';
import { MainLayout } from '@/components/layout';
import { GlassCard, PageHeader, Input, Button } from '@/components/ui';

export default function JoinCoursePage() {
    const router = useRouter();
    const { joinCourse, error, clearError } = useCourseStore();

    const [identifier, setIdentifier] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        clearError();
        setIsSubmitting(true);

        try {
            await joinCourse(identifier);
            // Redirect to courses page
            router.push('/courses');
        } catch (err) {
            console.error('Failed to join course:', err);
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
                    title="Join a Course"
                    subtitle="Enter a course code or invite link to join"
                />

                <GlassCard>
                    {error && (
                        <div className="mb-6 px-4 py-3 bg-[var(--error)]/10 border border-[var(--error)]/20 rounded-lg">
                            <p className="text-sm text-[var(--error)]">{error}</p>
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-5">
                        <Input
                            label="Course Code or Invite Link"
                            type="text"
                            placeholder="HIST 101 or course-invite-code"
                            value={identifier}
                            onChange={(e) => setIdentifier(e.target.value)}
                            required
                        />

                        <div className="bg-[var(--bg-sunken)] p-4 rounded-lg">
                            <p className="text-sm text-[var(--text-secondary)] mb-2">
                                <strong>How to join:</strong>
                            </p>
                            <ul className="text-sm text-[var(--text-tertiary)] space-y-1 list-disc list-inside">
                                <li>Enter the course code (e.g., HIST 101)</li>
                                <li>Or paste an invite link from your instructor</li>
                            </ul>
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
                                {isSubmitting ? 'Joining...' : 'Join Course'}
                            </Button>
                        </div>
                    </form>
                </GlassCard>
            </div>
        </MainLayout>
    );
}
