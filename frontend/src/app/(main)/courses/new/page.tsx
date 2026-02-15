/**
 * NotesOS - Create Course Page
 * Form to create a new course
 */

'use client';

import { useState, FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { useCourseStore } from '@/stores/courses';
import { MainLayout } from '@/components/layout';
import { GlassCard, PageHeader, Input, Button } from '@/components/ui';

export default function CreateCoursePage() {
    const router = useRouter();
    const { createCourse, error, clearError } = useCourseStore();

    const [code, setCode] = useState('');
    const [name, setName] = useState('');
    const [description, setDescription] = useState('');
    const [university, setUniversity] = useState('');
    const [isSubmitting, setIsSubmitting] = useState(false);

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        clearError();
        setIsSubmitting(true);

        try {
            const course = await createCourse({
                code,
                name,
                description: description || undefined,
                university: university || undefined,
            });

            // Redirect to the new course
            router.push(`/courses/${course.id}`);
        } catch (err) {
            console.error('Failed to create course:', err);
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
                    title="Create a Course"
                    subtitle="Set up a new course for your study group"
                />

                <GlassCard>
                    {error && (
                        <div className="mb-6 px-4 py-3 bg-[var(--error)]/10 border border-[var(--error)]/20 rounded-lg">
                            <p className="text-sm text-[var(--error)]">{error}</p>
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-5">
                        <Input
                            label="Course Code"
                            type="text"
                            placeholder="HIST 101"
                            value={code}
                            onChange={(e) => setCode(e.target.value)}
                            required
                        />

                        <Input
                            label="Course Name"
                            type="text"
                            placeholder="Introduction to World History"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            required
                        />

                        {/* <div className="flex flex-col gap-1.5">
                            <label className="text-sm font-medium text-[var(--text-primary)]">
                                Description (optional)
                            </label>
                            <textarea
                                className="px-4 py-2.5 bg-[var(--bg-sunken)] border-0 rounded-lg text-base text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)] transition-all resize-none"
                                placeholder="Brief description of the course..."
                                rows={4}
                                value={description}
                                onChange={(e) => setDescription(e.target.value)}
                            />
                        </div>

                        <Input
                            label="University (optional)"
                            type="text"
                            placeholder="Stanford University"
                            value={university}
                            onChange={(e) => setUniversity(e.target.value)}
                        /> */}

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
                                {isSubmitting ? 'Creating...' : 'Create Course'}
                            </Button>
                        </div>
                    </form>
                </GlassCard>
            </div>
        </MainLayout>
    );
}
