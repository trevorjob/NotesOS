/**
 * Topic Study View - REDESIGNED
 * Single-column layout: Collapsible Research + Resources (main content) + Floating AI Chat
 */

'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, BookOpen, FileText, Sparkles, Loader2, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react';
import { useCourseStore } from '@/stores/courses';
import { useResourcesStore } from '@/stores/resources';
import { useAIChatStore } from '@/stores/aiChat';
import { useAuthStore } from '@/stores/auth';
import { GlassCard, Button } from '@/components/ui';
import { ResourceCard } from '@/components/ResourceCard';
import { FileUpload } from '@/components/FileUpload';
import { AIChatOverlay } from '@/components/AIChatOverlay';
import { MarkdownRenderer } from '@/components/MarkdownRenderer';
import { api } from '@/lib/api';

export default function TopicPage() {
    const params = useParams();
    const router = useRouter();
    const courseId = params.courseId as string;
    const topicId = params.topicId as string;

    const { currentCourse } = useCourseStore();
    const { user } = useAuthStore();
    const {
        resources,
        isLoading: resourcesLoading,
        isUploading,
        uploadProgress,
        fetchResources,
        uploadFiles,
        deleteResource,
        factCheckResource,
    } = useResourcesStore();

    const {
        messages,
        isSending,
        fetchConversations,
        askQuestion,
        clearCurrentConversation,
    } = useAIChatStore();

    const [topic, setTopic] = useState<any>(null);
    const [research, setResearch] = useState<any>(null);
    const [isResearchExpanded, setIsResearchExpanded] = useState(false);
    const [researchLoading, setResearchLoading] = useState(false);
    const [generatingResearch, setGeneratingResearch] = useState(false);

    // Load topic data
    useEffect(() => {
        const loadTopic = async () => {
            try {
                const response = await api.topics.getById(topicId);
                setTopic(response.data);
            } catch (error) {
                console.error('Failed to load topic:', error);
            }
        };
        loadTopic();
    }, [topicId]);

    // Load resources
    useEffect(() => {
        fetchResources(topicId);
    }, [topicId, fetchResources]);

    // Load research
    useEffect(() => {
        const loadResearch = async () => {
            setResearchLoading(true);
            try {
                const response = await api.ai.getResearch(topicId);
                setResearch(response.data);
            } catch (error) {
                // Research doesn't exist yet
                setResearch(null);
            } finally {
                setResearchLoading(false);
            }
        };
        loadResearch();
    }, [topicId]);

    // Load conversations
    useEffect(() => {
        if (courseId) {
            fetchConversations(courseId);
        }
        return () => clearCurrentConversation();
    }, [courseId, fetchConversations, clearCurrentConversation]);

    const handleGenerateResearch = async () => {
        setGeneratingResearch(true);
        try {
            const response = await api.ai.generateResearch(topicId);
            setResearch(response.data);
            setIsResearchExpanded(true); // Auto-expand after generation
        } catch (error) {
            console.error('Failed to generate research:', error);
        } finally {
            setGeneratingResearch(false);
        }
    };

    const handleUpload = async (files: File[], title?: string, isHandwritten?: boolean) => {
        await uploadFiles(topicId, courseId, files, title, isHandwritten);
    };

    const handleAskQuestion = async (question: string) => {
        await askQuestion(courseId, question, topicId);
    };

    const handleDeleteResource = async (resourceId: string) => {
        if (confirm('Delete this resource?')) {
            try {
                await deleteResource(resourceId);
            } catch (error) {
                console.error('Failed to delete resource:', error);
            }
        }
    };

    const handleFactCheck = async (resourceId: string) => {
        try {
            await factCheckResource(resourceId);
            alert('Fact check started! Check back later for results.');
        } catch (error) {
            console.error('Failed to start fact check:', error);
        }
    };

    if (!topic) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <p className="text-[var(--text-tertiary)]">Loading topic...</p>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-[var(--bg-base)] pt-16">
            {/* Header */}
            <div className="border-b border-[var(--glass-border)] bg-[var(--bg-base)]/80 backdrop-blur-md sticky top-16 z-30">
                <div className="max-w-5xl mx-auto px-6 md:px-12 py-4">
                    <button
                        onClick={() => router.push(`/courses/${courseId}`)}
                        className="flex items-center gap-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] mb-3 transition-colors"
                    >
                        <ArrowLeft className="w-4 h-4" />
                        Back to {currentCourse?.code || 'Course'}
                    </button>
                    <div>
                        <h1 className="text-2xl md:text-3xl font-semibold text-[var(--text-primary)]">
                            {topic.title}
                        </h1>
                        {topic.week_number && (
                            <p className="text-sm text-[var(--text-tertiary)] mt-1">Week {topic.week_number}</p>
                        )}
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <div className="max-w-5xl mx-auto px-6 md:px-12 py-8 space-y-6">
                {/* Pre-class Research (Collapsible) */}
                {research || researchLoading || !research ? (
                    <GlassCard className="overflow-hidden">
                        <button
                            onClick={() => setIsResearchExpanded(!isResearchExpanded)}
                            className="w-full flex items-center justify-between p-5 text-left hover:bg-[var(--bg-sunken)]/30 transition-colors"
                        >
                            <div className="flex items-center gap-3">
                                <div className="w-10 h-10 rounded-full bg-[var(--accent-primary)]/10 flex items-center justify-center">
                                    <BookOpen className="w-5 h-5 text-[var(--accent-primary)]" />
                                </div>
                                <div>
                                    <h2 className="text-lg font-medium text-[var(--text-primary)]">
                                        Pre-class Research
                                    </h2>
                                    <p className="text-xs text-[var(--text-tertiary)] mt-0.5">
                                        {research ? 'AI-generated overview and key concepts' : 'Generate AI research for this topic'}
                                    </p>
                                </div>
                            </div>
                            {research && (
                                isResearchExpanded ? <ChevronUp className="w-5 h-5 text-[var(--text-secondary)]" /> : <ChevronDown className="w-5 h-5 text-[var(--text-secondary)]" />
                            )}
                        </button>

                        {isResearchExpanded && (
                            <div className="px-5 pb-5 space-y-4 border-t border-[var(--glass-border)] pt-5">
                                {researchLoading ? (
                                    <div className="text-center py-8">
                                        <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-[var(--text-tertiary)]" />
                                        <p className="text-sm text-[var(--text-tertiary)]">Loading...</p>
                                    </div>
                                ) : research ? (
                                    <>
                                        {/* Research content */}
                                        <MarkdownRenderer content={research.research_content} />

                                        {/* Key concepts */}
                                        {research.key_concepts?.concepts && research.key_concepts.concepts.length > 0 && (
                                            <div>
                                                <h3 className="text-sm font-medium text-[var(--text-primary)] mb-3">
                                                    Key Concepts
                                                </h3>
                                                <div className="flex flex-wrap gap-2">
                                                    {research.key_concepts.concepts.map((concept: string, idx: number) => (
                                                        <span
                                                            key={idx}
                                                            className="px-3 py-1.5 rounded-full bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] text-sm font-medium"
                                                        >
                                                            {concept}
                                                        </span>
                                                    ))}
                                                </div>
                                            </div>
                                        )}

                                        {/* Sources */}
                                        {research.sources && research.sources.length > 0 && (
                                            <div>
                                                <h3 className="text-sm font-medium text-[var(--text-primary)] mb-3">
                                                    Sources
                                                </h3>
                                                <div className="space-y-2">
                                                    {research.sources.map((source: any, idx: number) => (
                                                        <a
                                                            key={idx}
                                                            href={source.url}
                                                            target="_blank"
                                                            rel="noopener noreferrer"
                                                            className="flex items-center gap-2 text-sm text-[var(--accent-primary)] hover:underline"
                                                        >
                                                            <ExternalLink className="w-3 h-3" />
                                                            {source.title || source.url}
                                                        </a>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </>
                                ) : (
                                    <div className="text-center py-8">
                                        <Sparkles className="w-12 h-12 mx-auto mb-4 text-[var(--text-tertiary)]" />
                                        <p className="text-sm text-[var(--text-secondary)] mb-4">
                                            No pre-class research yet
                                        </p>
                                        <Button
                                            onClick={handleGenerateResearch}
                                            variant="primary"
                                            disabled={generatingResearch}
                                        >
                                            {generatingResearch ? 'Generating...' : 'Generate Research'}
                                        </Button>
                                    </div>
                                )}
                            </div>
                        )}
                    </GlassCard>
                ) : null}

                {/* Resources Section (Main Content) */}
                <div>
                    <div className="flex items-center gap-3 mb-4">
                        <div className="w-10 h-10 rounded-full bg-[var(--accent-primary)]/10 flex items-center justify-center">
                            <FileText className="w-5 h-5 text-[var(--accent-primary)]" />
                        </div>
                        <div>
                            <h2 className="text-lg font-medium text-[var(--text-primary)]">
                                Study Resources
                            </h2>
                            <p className="text-xs text-[var(--text-tertiary)] mt-0.5">
                                Upload and manage your study materials
                            </p>
                        </div>
                    </div>

                    {/* Upload */}
                    <div className="mb-6">
                        <FileUpload
                            onUpload={handleUpload}
                            isUploading={isUploading}
                            uploadProgress={uploadProgress}
                        />
                    </div>

                    {/* Resource list */}
                    {resourcesLoading ? (
                        <GlassCard className="p-8 text-center">
                            <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-[var(--text-tertiary)]" />
                            <p className="text-sm text-[var(--text-tertiary)]">Loading resources...</p>
                        </GlassCard>
                    ) : resources.length === 0 ? (
                        <GlassCard className="p-12 text-center">
                            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-[var(--bg-sunken)] flex items-center justify-center">
                                <FileText className="w-8 h-8 text-[var(--text-tertiary)]" />
                            </div>
                            <p className="text-sm text-[var(--text-secondary)] mb-1">No resources yet</p>
                            <p className="text-xs text-[var(--text-tertiary)]">
                                Upload your notes, PDFs, or images to get started
                            </p>
                        </GlassCard>
                    ) : (
                        <div className="space-y-3">
                            {resources.map((resource) => (
                                <ResourceCard
                                    key={resource.id}
                                    resource={resource}
                                    currentUserId={user?.id}
                                    onDelete={handleDeleteResource}
                                    onFactCheck={handleFactCheck}
                                />
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {/* Floating AI Chat Overlay */}
            <AIChatOverlay
                messages={messages}
                onSendMessage={handleAskQuestion}
                isLoading={isSending}
                courseId={courseId}
            />
        </div>
    );
}
