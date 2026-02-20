/**
 * Course Home Page
 * Shows topic list with mastery indicators and add topic form
 */

'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { Plus, BookOpen, Users, TrendingUp } from 'lucide-react';
import { useCourseStore } from '@/stores/courses';
import { useProgressStore } from '@/stores/progress';
import { GlassCard, Button } from '@/components/ui';
import { MainLayout } from '@/components/layout';
import { api } from '@/lib/api';

export default function CoursePage() {
    const params = useParams();
    const router = useRouter();
    const courseId = params.courseId as string;

    const { currentCourse, isLoading, selectCourse, createTopic, updateTopic, deleteTopic } = useCourseStore();
    const { streak, fetchStreak } = useProgressStore();
    const [showAddTopic, setShowAddTopic] = useState(false);
    const [newTopicTitle, setNewTopicTitle] = useState('');
    const [newTopicDescription, setNewTopicDescription] = useState('');
    const [newTopicWeek, setNewTopicWeek] = useState<number | ''>('');
    const [isCreating, setIsCreating] = useState(false);

    const [editingTopicId, setEditingTopicId] = useState<string | null>(null);
    const [editTitle, setEditTitle] = useState('');
    const [editDescription, setEditDescription] = useState('');
    const [editWeek, setEditWeek] = useState<number | ''>('');
    const [isUpdating, setIsUpdating] = useState(false);

    const [batchTopicsText, setBatchTopicsText] = useState('');
    const [batchTopicsError, setBatchTopicsError] = useState<string | null>(null);
    const [isBatchCreating, setIsBatchCreating] = useState(false);

    useEffect(() => {
        selectCourse(courseId);
    }, [courseId, selectCourse]);

    useEffect(() => {
        if (courseId) fetchStreak(courseId);
    }, [courseId, fetchStreak]);

    const handleCreateTopic = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!newTopicTitle.trim() || !currentCourse) return;

        setIsCreating(true);
        try {
            const nextOrderIndex = currentCourse.topics?.length || 0;
            await createTopic(courseId, {
                title: newTopicTitle,
                description: newTopicDescription || undefined,
                week_number: typeof newTopicWeek === 'number' ? newTopicWeek : undefined,
                order_index: nextOrderIndex,
            });
            setNewTopicTitle('');
            setNewTopicDescription('');
            setNewTopicWeek('');
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

    const startEditingTopic = (topic: any) => {
        setEditingTopicId(topic.id);
        setEditTitle(topic.title || '');
        setEditDescription(topic.description || '');
        setEditWeek(typeof topic.week_number === 'number' ? topic.week_number : '');
    };

    const handleUpdateTopic = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!editingTopicId || !currentCourse) return;
        if (!editTitle.trim()) return;

        setIsUpdating(true);
        try {
            await updateTopic(currentCourse.id, editingTopicId, {
                title: editTitle,
                description: editDescription || undefined,
                week_number: typeof editWeek === 'number' ? editWeek : undefined,
            });
            setEditingTopicId(null);
            setEditTitle('');
            setEditDescription('');
            setEditWeek('');
        } catch (error) {
            console.error('Failed to update topic:', error);
        } finally {
            setIsUpdating(false);
        }
    };

    const handleDeleteTopic = async (topicId: string) => {
        if (!currentCourse) return;
        const confirmed = window.confirm('Delete this topic? This will remove all its notes.');
        if (!confirmed) return;
        try {
            await deleteTopic(currentCourse.id, topicId);
        } catch (error) {
            console.error('Failed to delete topic:', error);
        }
    };

    const handleBatchCreateTopics = async () => {
        if (!currentCourse) return;
        setBatchTopicsError(null);
        if (!batchTopicsText.trim()) {
            setBatchTopicsError('Paste some JSON describing your topics.');
            return;
        }
        let parsed: Array<{ title: string; week_number?: number; order_index?: number }>;
        try {
            parsed = JSON.parse(batchTopicsText);
            if (!Array.isArray(parsed)) {
                throw new Error('Expected an array of topics');
            }
        } catch (e: any) {
            setBatchTopicsError(e.message || 'Invalid JSON');
            return;
        }

        const startIndex = currentCourse.topics?.length || 0;
        const topicsPayload = parsed.map((t, index) => ({
            title: t.title,
            week_number: t.week_number,
            order_index: typeof t.order_index === 'number' ? t.order_index : startIndex + index,
        }));

        setIsBatchCreating(true);
        try {
            await api.topics.batchCreate(currentCourse.id, topicsPayload);
            await selectCourse(currentCourse.id);
            setBatchTopicsText('');
        } catch (error) {
            console.error('Failed to batch create topics:', error);
            setBatchTopicsError('Failed to create topics. Check your JSON and try again.');
        } finally {
            setIsBatchCreating(false);
        }
    };

    if (isLoading) {
        return (
            <MainLayout
                currentCourse={currentCourse ? { id: currentCourse.id, code: currentCourse.code, name: currentCourse.name } : undefined}
                streak={streak}
            >
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
        <MainLayout
            currentCourse={{ id: currentCourse.id, code: currentCourse.code, name: currentCourse.name }}
            streak={streak}
        >
            <div className="max-w-[1400px] mx-auto px-8 md:px-20 py-12">
                {/* Header */}
                <div className="mb-8">
                    <div className="flex items-start justify-between mb-4 flex-wrap gap-4">
                        <div>
                            <h1 className="text-3xl font-semibold text-[var(--text-primary)] mb-2">
                                {currentCourse.name}
                            </h1>
                            <p className="text-[var(--text-secondary)]">{currentCourse.code}</p>
                        </div>
                        <div className="flex items-center gap-3">
                            <Link href={`/courses/${courseId}/progress`}>
                                <Button variant="secondary">
                                    <TrendingUp className="w-4 h-4 mr-2 inline" />
                                    Progress
                                </Button>
                            </Link>
                            <Link href={`/courses/${courseId}/tests`}>
                                <Button variant="secondary">
                                    Practice Test
                                </Button>
                            </Link>
                        </div>
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
                                <div
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
                                        <div className="flex items-center gap-3 mb-3">
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

                                        {/* Topic actions */}
                                        <div className="flex items-center justify-between gap-2 text-xs">
                                            {typeof topic.week_number === 'number' && (
                                                <span className="text-[var(--text-tertiary)]">
                                                    Week {topic.week_number}
                                                </span>
                                            )}
                                            <div className="ml-auto flex items-center gap-2">
                                                <button
                                                    type="button"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        startEditingTopic(topic);
                                                    }}
                                                    className="px-2 py-1 rounded bg-[var(--bg-sunken)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
                                                >
                                                    Edit
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        handleDeleteTopic(topic.id);
                                                    }}
                                                    className="px-2 py-1 rounded bg-[var(--bg-sunken)] text-[var(--error)] hover:bg-[var(--error)]/10 transition-colors"
                                                >
                                                    Delete
                                                </button>
                                            </div>
                                        </div>
                                    </GlassCard>
                                </div>
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
                                    <textarea
                                        value={newTopicDescription}
                                        onChange={(e) => setNewTopicDescription(e.target.value)}
                                        placeholder="Short description (optional)"
                                        rows={3}
                                        className="w-full px-4 py-2.5 bg-[var(--bg-sunken)] border border-[var(--glass-border)] rounded text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)] resize-none"
                                    />
                                    <div className="flex items-center gap-3">
                                        <div className="flex-1">
                                            <label className="block text-xs text-[var(--text-tertiary)] mb-1">
                                                Week number (optional)
                                            </label>
                                            <input
                                                type="number"
                                                min={1}
                                                value={newTopicWeek === '' ? '' : newTopicWeek}
                                                onChange={(e) => {
                                                    const value = e.target.value;
                                                    setNewTopicWeek(value === '' ? '' : Number(value));
                                                }}
                                                className="w-full px-3 py-2 bg-[var(--bg-sunken)] border border-[var(--glass-border)] rounded text-xs text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
                                            />
                                        </div>
                                    </div>
                                    <div className="flex gap-2 pt-1">
                                        <Button type="submit" variant="primary" disabled={isCreating || !newTopicTitle.trim()}>
                                            {isCreating ? 'Creating...' : 'Create Topic'}
                                        </Button>
                                        <Button
                                            type="button"
                                            variant="secondary"
                                            onClick={() => {
                                                setShowAddTopic(false);
                                                setNewTopicTitle('');
                                                setNewTopicDescription('');
                                                setNewTopicWeek('');
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

                        {editingTopicId && (
                            <GlassCard className="p-5">
                                <form onSubmit={handleUpdateTopic} className="space-y-3">
                                    <p className="text-sm font-medium text-[var(--text-primary)] mb-1">
                                        Edit topic
                                    </p>
                                    <input
                                        type="text"
                                        value={editTitle}
                                        onChange={(e) => setEditTitle(e.target.value)}
                                        placeholder="Topic title"
                                        required
                                        className="w-full px-4 py-2.5 bg-[var(--bg-sunken)] border border-[var(--glass-border)] rounded text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
                                    />
                                    <textarea
                                        value={editDescription}
                                        onChange={(e) => setEditDescription(e.target.value)}
                                        placeholder="Short description (optional)"
                                        rows={3}
                                        className="w-full px-4 py-2.5 bg-[var(--bg-sunken)] border border-[var(--glass-border)] rounded text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)] resize-none"
                                    />
                                    <div className="flex items-center gap-3">
                                        <div className="flex-1">
                                            <label className="block text-xs text-[var(--text-tertiary)] mb-1">
                                                Week number (optional)
                                            </label>
                                            <input
                                                type="number"
                                                min={1}
                                                value={editWeek === '' ? '' : editWeek}
                                                onChange={(e) => {
                                                    const value = e.target.value;
                                                    setEditWeek(value === '' ? '' : Number(value));
                                                }}
                                                className="w-full px-3 py-2 bg-[var(--bg-sunken)] border border-[var(--glass-border)] rounded text-xs text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
                                            />
                                        </div>
                                    </div>
                                    <div className="flex gap-2 pt-1">
                                        <Button type="submit" variant="primary" disabled={isUpdating || !editTitle.trim()}>
                                            {isUpdating ? 'Saving...' : 'Save changes'}
                                        </Button>
                                        <Button
                                            type="button"
                                            variant="secondary"
                                            onClick={() => {
                                                setEditingTopicId(null);
                                                setEditTitle('');
                                                setEditDescription('');
                                                setEditWeek('');
                                            }}
                                        >
                                            Cancel
                                        </Button>
                                    </div>
                                </form>
                            </GlassCard>
                        )}

                        {/* Batch create topics (optional power feature) */}
                        <GlassCard className="p-5">
                            <div className="flex items-center justify-between mb-3 gap-2">
                                <p className="text-sm font-medium text-[var(--text-primary)]">
                                    Batch create topics
                                </p>
                                <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--bg-sunken)] text-[var(--text-tertiary)] uppercase tracking-wide">
                                    Optional
                                </span>
                            </div>
                            <p className="text-xs text-[var(--text-secondary)] mb-2">
                                Paste a JSON array of topics. Each item should include at least <code>title</code> and
                                can optionally include <code>week_number</code> and <code>order_index</code>.
                            </p>
                            <textarea
                                value={batchTopicsText}
                                onChange={(e) => setBatchTopicsText(e.target.value)}
                                rows={5}
                                className="w-full px-4 py-2.5 bg-[var(--bg-sunken)] border border-[var(--glass-border)] rounded text-xs text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)] font-mono"
                                placeholder={`[
  { "title": "Week 1 – Introduction", "week_number": 1 },
  { "title": "Week 2 – Key Concepts", "week_number": 2 }
]`}
                            />
                            {batchTopicsError && (
                                <p className="mt-1 text-xs text-[var(--error)]">{batchTopicsError}</p>
                            )}
                            <div className="flex justify-end gap-2 mt-3">
                                <Button
                                    type="button"
                                    variant="secondary"
                                    onClick={() => {
                                        setBatchTopicsText('');
                                        setBatchTopicsError(null);
                                    }}
                                    disabled={isBatchCreating}
                                >
                                    Clear
                                </Button>
                                <Button
                                    type="button"
                                    variant="primary"
                                    onClick={handleBatchCreateTopics}
                                    disabled={isBatchCreating || !batchTopicsText.trim()}
                                >
                                    {isBatchCreating ? 'Creating...' : 'Create topics'}
                                </Button>
                            </div>
                        </GlassCard>
                    </div>
                )}
            </div>
        </MainLayout>
    );
}
