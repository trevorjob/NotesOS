/**
 * NotesOS - All Courses Page
 * Grid view of all enrolled courses
 */

'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Plus } from 'lucide-react';
import { useCourseStore } from '@/stores/courses';
import { MainLayout } from '@/components/layout';
import { GlassCard, PageHeader, Button, Skeleton, Badge } from '@/components/ui';

export default function CoursesPage() {
    const router = useRouter();
    const { courses, isLoading, fetchCourses, selectCourse } = useCourseStore();

    useEffect(() => {
        fetchCourses();
    }, [fetchCourses]);

    const handleCourseClick = async (courseId: string) => {
        await selectCourse(courseId);
        router.push(`/courses/${courseId}`);
    };

    return (
        <MainLayout>
            <div className="max-w-7xl mx-auto px-8 md:px-20 py-12">
                <PageHeader
                    title="Your Courses"
                    subtitle="All your enrolled courses"
                    action={
                        <div className="flex gap-3">
                            <Link href="/courses/join">
                                <Button variant="secondary">Join Course</Button>
                            </Link>
                            <Link href="/courses/new">
                                <Button variant="primary">
                                    <Plus className="w-4 h-4 mr-2" />
                                    Create Course
                                </Button>
                            </Link>
                        </div>
                    }
                />

                {isLoading ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {[1, 2, 3].map((i) => (
                            <Skeleton key={i} className="h-48" />
                        ))}
                    </div>
                ) : courses.length === 0 ? (
                    <GlassCard className="text-center py-16">
                        <p className="text-lg text-[var(--text-secondary)] mb-6">
                            You haven't joined any courses yet
                        </p>
                        <div className="flex gap-3 justify-center">
                            <Link href="/courses/join">
                                <Button variant="secondary">Join a Course</Button>
                            </Link>
                            <Link href="/courses/new">
                                <Button variant="primary">Create Your First Course</Button>
                            </Link>
                        </div>
                    </GlassCard>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {courses.map((course) => (
                            <button
                                key={course.id}
                                onClick={() => handleCourseClick(course.id)}
                                className="text-left w-full"
                            >
                                <GlassCard hover className="cursor-pointer h-full">
                                    <div className="flex items-start justify-between mb-4">
                                        <div>
                                            <h3 className="text-lg font-semibold text-[var(--text-primary)] mb-1">
                                                {course.code}
                                            </h3>
                                            <p className="text-sm text-[var(--text-secondary)]">
                                                {course.name}
                                            </p>
                                        </div>
                                        {course.member_count && (
                                            <Badge variant="default">
                                                {course.member_count} {course.member_count === 1 ? 'member' : 'members'}
                                            </Badge>
                                        )}
                                    </div>

                                    {course.description && (
                                        <p className="text-sm text-[var(--text-tertiary)] line-clamp-2 mb-4">
                                            {course.description}
                                        </p>
                                    )}
                                </GlassCard>
                            </button>
                        ))}
                    </div>
                )}
            </div>
        </MainLayout>
    );
}
