/**
 * Course Home Page
 * Shows topic list with mastery indicators and add topic form
 */

'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { Plus, BookOpen, Users } from 'lucide-react';
import { useCourseStore } from '@/stores/courses';
import { useAuthStore } from '@/stores/auth';
import { GlassCard, Button } from '@/components/ui';
import { MainLayout } from '@/components/layout';

export default function CoursePage() {
    const params = useParams();
    const router = useRouter();
    const courseId = params.courseId as string;

    const { currentCourse, isLoading, selectCourse, createTopic } = useCourseStore();
    const { user } = useAuthStore();
    const [showAddTopic, setShowAddTopic] = useState(false);
    const [newTopicTitle, setNewTopicTitle] = useState('');
    const [isCreating, setIsCreating] = useState(false);

    useEffect(() => {
        selectCourse(courseId);
    }, [courseId, selectCourse]);

    const handleCreateTopic = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!newTopicTitle.trim() || !currentCourse) return;

        setIsCreating(true);
        try {
            const nextOrderIndex = currentCourse.topics?.length || 0;
            await createTopic(courseId, {
                title: newTopicTitle,
                order_index: nextOrderIndex,
            });
            setNewTopicTitle('');
            setShowAddTopic(false);
        } catch (error) {
            console.error('Failed to create topic:', error);
        } finally {
            setIsCreating(false);
        }
    };

    const getMasteryColor = (level?: number) => {
        if (!level) return 'var(--bg-sunken)';
        if (level < 30) return 'var(--error)';
        if (level < 70) return 'var(--accent-secondary)';
        return 'var(--success)';
    };

    if (isLoading) {
        return (
            <MainLayout currentCourse={currentCourse ? { id: currentCourse.id, code: currentCourse.code, name: currentCourse.name } : undefined}>
                <div className="flex items-center justify-center min-h-[60vh]">
                    <p className="text-[var(--text-tertiary)]">Loading course...</p>
                </div>
            </MainLayout>
        );
    }

    if (!currentCourse) {
        return (
            <MainLayout>
                <div className="flex items-center justify-center min-h-[60vh]">
                    <p className="text-[var(--text-tertiary)]">Course not found</p>
                </div>
            </MainLayout>
        );
    }

    const topics = currentCourse.topics || [];

    return (
        <MainLayout currentCourse={{ id: currentCourse.id, code: currentCourse.code, name: currentCourse.name }}>
            <div className="max-w-[1400px] mx-auto px-8 md:px-20 py-12">
                {/* Header */}
                <div className="mb-8">
                    <div className="flex items-start justify-between mb-4">
                        <div>
                            <h1 className="text-3xl font-semibold text-[var(--text-primary)] mb-2">
                                {currentCourse.name}
                            </h1>
                            <p className="text-[var(--text-secondary)]">{currentCourse.code}</p>
                        </div>
                        <div className="flex items-center gap-4 text-sm text-[var(--text-tertiary)]">
                            {currentCourse.semester && (
                                <span className="flex items-center gap-1">
                                    <BookOpen className="w-4 h-4" />
                                    {currentCourse.semester}
                                </span>
                            )}
                            {currentCourse.member_count && (
                                <span className="flex items-center gap-1">
                                    <Users className="w-4 h-4" />
                                    {currentCourse.member_count} members
                                </span>
                            )}
                        </div>
                    </div>
                    {currentCourse.description && (
                        <p className="text-[var(--text-secondary)] max-w-3xl">{currentCourse.description}</p>
                    )}
                </div>

                {/* Topics Grid */}
                {topics.length === 0 && !showAddTopic ? (
                    <div className="text-center py-16">
                        <p className="text-[var(--text-tertiary)] mb-4">No topics yet</p>
                        <Button onClick={() => setShowAddTopic(true)} variant="primary">
                            <Plus className="w-4 h-4 mr-2" />
                            Create First Topic
                        </Button>
                    </div>
                ) : (
                    <div className="space-y-6">
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {topics.map((topic) => (
                                <button
                                    key={topic.id}
                                    onClick={() => router.push(`/courses/${courseId}/topics/${topic.id}`)}
                                    className="text-left w-full"
                                >
                                    <GlassCard className="p-5 cursor-pointer hover:shadow-lg transition-all h-full">
                                        {/* Week badge */}
                                        {topic.week_number && (
                                            <div className="mb-3">
                                                <span className="text-xs px-2 py-1 rounded-full bg-[var(--bg-sunken)] text-[var(--text-tertiary)]">
                                                    Week {topic.week_number}
                                                </span>
                                            </div>
                                        )}

                                        {/* Title */}
                                        <h3 className="text-lg font-medium text-[var(--text-primary)] mb-2">
                                            {topic.title}
                                        </h3>

                                        {/* Description */}
                                        {topic.description && (
                                            <p className="text-sm text-[var(--text-secondary)] mb-4 line-clamp-2">
                                                {topic.description}
                                            </p>
                                        )}

                                        {/* Mastery indicator */}
                                        <div className="flex items-center gap-3">
                                            <div className="flex-1">
                                                <div className="h-1.5 bg-[var(--bg-sunken)] rounded-full overflow-hidden">
                                                    <div
                                                        className="h-full transition-all duration-300"
                                                        style={{
                                                            width: `${topic.mastery_level || 0}%`,
                                                            backgroundColor: getMasteryColor(topic.mastery_level),
                                                        }}
                                                    />
                                                </div>
                                            </div>
                                            <span className="text-xs text-[var(--text-tertiary)] font-medium">
                                                {topic.mastery_level || 0}%
                                            </span>
                                        </div>
                                    </GlassCard>
                                </button>
                            ))}
                        </div>

                        {/* Add Topic Section */}
                        {showAddTopic ? (
                            <GlassCard className="p-5">
                                <form onSubmit={handleCreateTopic} className="space-y-3">
                                    <input
                                        type="text"
                                        value={newTopicTitle}
                                        onChange={(e) => setNewTopicTitle(e.target.value)}
                                        placeholder="Topic title"
                                        required
                                        className="w-full px-4 py-2.5 bg-[var(--bg-sunken)] border border-[var(--glass-border)] rounded text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
                                    />
                                    <div className="flex gap-2">
                                        <Button type="submit" variant="primary" disabled={isCreating || !newTopicTitle.trim()}>
                                            {isCreating ? 'Creating...' : 'Create Topic'}
                                        </Button>
                                        <Button
                                            type="button"
                                            variant="secondary"
                                            onClick={() => {
                                                setShowAddTopic(false);
                                                setNewTopicTitle('');
                                            }}
                                        >
                                            Cancel
                                        </Button>
                                    </div>
                                </form>
                            </GlassCard>
                        ) : (
                            <button
                                onClick={() => setShowAddTopic(true)}
                                className="w-full p-4 border-2 border-dashed border-[var(--glass-border)] rounded-lg text-[var(--text-tertiary)] hover:border-[var(--accent-primary)] hover:text-[var(--accent-primary)] transition-colors flex items-center justify-center gap-2"
                            >
                                <Plus className="w-5 h-5" />
                                Add Topic
                            </button>
                        )}
                    </div>
                )}
            </div>
        </MainLayout>
    );
}
