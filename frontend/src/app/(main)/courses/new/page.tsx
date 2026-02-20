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
import { api } from '@/lib/api';

export default function CreateCoursePage() {
    const router = useRouter();
    const { createCourse, error, clearError, fetchCourses } = useCourseStore();

    const [mode, setMode] = useState<'single' | 'batch'>('single');
    const [code, setCode] = useState('');
    const [name, setName] = useState('');
    const [description, setDescription] = useState('');
    const [batchText, setBatchText] = useState('');
    const [batchError, setBatchError] = useState<string | null>(null);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        clearError();
        setBatchError(null);
        setIsSubmitting(true);

        try {
            if (mode === 'batch') {
                if (!batchText.trim()) {
                    setBatchError('Paste some JSON describing your courses.');
                    setIsSubmitting(false);
                    return;
                }
                let parsed: Array<{ code: string; name: string; description?: string; semester?: string; is_public?: boolean }>;
                try {
                    parsed = JSON.parse(batchText);
                    if (!Array.isArray(parsed)) {
                        throw new Error('Expected an array of courses');
                    }
                } catch (e: any) {
                    setBatchError(e.message || 'Invalid JSON');
                    setIsSubmitting(false);
                    return;
                }

                await api.courses.batchCreate(parsed);
                await fetchCourses();
                router.push('/courses');
            } else {
                const course = await createCourse({
                    code,
                    name,
                    description: description || undefined,
                });

                router.push(`/courses/${course.id}`);
            }
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

                    <div className="space-y-5">
                        <div className="flex gap-2 mb-2">
                            <button
                                type="button"
                                onClick={() => {
                                    setMode('single');
                                    setBatchError(null);
                                }}
                                className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${mode === 'single'
                                        ? 'bg-[var(--accent-primary)] text-white'
                                        : 'bg-[var(--bg-sunken)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                                    }`}
                            >
                                Single course
                            </button>
                            <button
                                type="button"
                                onClick={() => {
                                    setMode('batch');
                                    setBatchError(null);
                                }}
                                className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${mode === 'batch'
                                        ? 'bg-[var(--accent-primary)] text-white'
                                        : 'bg-[var(--bg-sunken)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                                    }`}
                            >
                                Batch create
                            </button>
                        </div>

                        <form onSubmit={handleSubmit} className="space-y-5">
                            {mode === 'single' ? (
                                <>
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

                                    <div className="flex flex-col gap-1.5">
                                        <label className="text-sm font-medium text-[var(--text-primary)]">
                                            Description (optional)
                                        </label>
                                        <textarea
                                            className="px-4 py-2.5 bg-[var(--bg-sunken)] border border-[var(--glass-border)] rounded-lg text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)] transition-all resize-none"
                                            placeholder="Brief description of the course..."
                                            rows={4}
                                            value={description}
                                            onChange={(e) => setDescription(e.target.value)}
                                        />
                                    </div>
                                </>
                            ) : (
                                <>
                                    <div className="flex flex-col gap-1.5">
                                        <label className="text-sm font-medium text-[var(--text-primary)]">
                                            Courses JSON
                                        </label>
                                        <textarea
                                            className="px-4 py-2.5 bg-[var(--bg-sunken)] border border-[var(--glass-border)] rounded-lg text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)] transition-all font-mono"
                                            placeholder={`[
  { "code": "HIST 101", "name": "Intro to History" },
  { "code": "MATH 201", "name": "Calculus I" }
]`}
                                            rows={8}
                                            value={batchText}
                                            onChange={(e) => setBatchText(e.target.value)}
                                        />
                                        <p className="text-xs text-[var(--text-tertiary)]">
                                            Up to 10 courses at once. Each item should include at least <code>code</code> and <code>name</code>.
                                        </p>
                                        {batchError && (
                                            <p className="text-xs text-[var(--error)]">{batchError}</p>
                                        )}
                                    </div>
                                </>
                            )}

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
                                    {isSubmitting ? 'Creating...' : mode === 'batch' ? 'Create Courses' : 'Create Course'}
                                </Button>
                            </div>
                        </form>
                    </div>
                </GlassCard>
            </div>
        </MainLayout>
    );
}
