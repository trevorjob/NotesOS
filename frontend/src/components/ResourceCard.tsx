/**
 * Resource Card Component
 * Glass card displaying a resource with markdown rendering, metadata, OCR status, verification badge
 */

'use client';

import { useState } from 'react';
import { FileText, Image, File, Check, AlertTriangle, Trash2, ChevronDown, ChevronUp, Eye, X } from 'lucide-react';
import { GlassCard } from './ui';
import { MarkdownRenderer } from './MarkdownRenderer';

interface ResourceCardProps {
    resource: {
        id: string;
        title?: string;
        uploader_name: string;
        content: string;
        resource_type: string;
        is_processed: boolean;
        ocr_cleaned: boolean;
        is_verified: boolean;
        ocr_confidence?: number;
        created_at: string;
        uploaded_by: string;
        file_url?: string;
    };
    currentUserId?: string;
    onDelete?: (id: string) => void;
    onFactCheck?: (id: string) => void;
}

export function ResourceCard({ resource, currentUserId, onDelete, onFactCheck }: ResourceCardProps) {
    const [isExpanded, setIsExpanded] = useState(false);
    const [showFullView, setShowFullView] = useState(false);

    const timeAgo = (date: string) => {
        const seconds = Math.floor((Date.now() - new Date(date).getTime()) / 1000);
        if (seconds < 60) return 'just now';
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
        return `${Math.floor(seconds / 86400)}d ago`;
    };

    const getTypeIcon = () => {
        switch (resource.resource_type) {
            case 'pdf':
                return <FileText className="w-4 h-4" />;
            case 'image':
                return <Image className="w-4 h-4" />;
            default:
                return <File className="w-4 h-4" />;
        }
    };

    const canDelete = currentUserId === resource.uploaded_by;

    return (
        <>
            <GlassCard className="p-4 hover:shadow-md transition-shadow">
                {/* Header */}
                <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="flex-1 min-w-0">
                        <h3 className="text-sm font-medium text-[var(--text-primary)] truncate">
                            {resource.title || 'Untitled Resource'}
                        </h3>
                        <p className="text-xs text-[var(--text-tertiary)] mt-0.5">
                            {resource.uploader_name} · {timeAgo(resource.created_at)}
                        </p>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2 shrink-0">
                        <button
                            onClick={() => setShowFullView(true)}
                            className="text-xs px-2 py-1 rounded text-[var(--text-secondary)] hover:bg-[var(--bg-sunken)] transition-colors flex items-center gap-1"
                            title="View full resource"
                        >
                            <Eye className="w-3 h-3" />
                            View
                        </button>
                        {!resource.is_verified && onFactCheck && (
                            <button
                                onClick={() => onFactCheck(resource.id)}
                                className="text-xs px-2 py-1 rounded text-[var(--text-secondary)] hover:bg-[var(--bg-sunken)] transition-colors"
                                title="Verify with AI"
                            >
                                Verify
                            </button>
                        )}
                        {canDelete && onDelete && (
                            <button
                                onClick={() => onDelete(resource.id)}
                                className="p-1.5 rounded hover:bg-[var(--bg-sunken)] text-[var(--text-tertiary)] hover:text-[var(--error)] transition-colors"
                                title="Delete"
                            >
                                <Trash2 className="w-4 h-4" />
                            </button>
                        )}
                    </div>
                </div>

                {/* Badges */}
                <div className="flex flex-wrap items-center gap-2 mb-3">
                    {/* Type badge */}
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[var(--bg-sunken)] text-[var(--text-secondary)] text-xs">
                        {getTypeIcon()}
                        {resource.resource_type}
                    </span>

                    {/* OCR status */}
                    {resource.resource_type !== 'text' && (
                        <span className={`text-xs px-2 py-0.5 rounded-full ${resource.is_processed
                            ? 'bg-[var(--success)]/10 text-[var(--success)]'
                            : 'bg-[var(--bg-sunken)] text-[var(--text-tertiary)]'
                            }`}>
                            {resource.is_processed ? 'Processed' : 'Processing...'}
                        </span>
                    )}

                    {/* Verification badge with more detail */}
                    {resource.is_verified ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[var(--success)]/10 text-[var(--success)] text-xs">
                            <Check className="w-3 h-3" />
                            AI Verified
                        </span>
                    ) : resource.ocr_confidence && resource.ocr_confidence < 0.8 ? (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[var(--error)]/10 text-[var(--error)] text-xs"
                            title={`OCR Confidence: ${Math.round(resource.ocr_confidence * 100)}%`}
                        >
                            <AlertTriangle className="w-3 h-3" />
                            Low confidence ({Math.round(resource.ocr_confidence * 100)}%)
                        </span>
                    ) : null}
                </div>

                {/* Content preview (markdown rendered, expandable) */}
                <div className="text-sm">
                    {isExpanded ? (
                        <MarkdownRenderer content={resource.content} className="max-h-96 overflow-y-auto" />
                    ) : (
                        <div className="line-clamp-3 text-[var(--text-secondary)]">
                            {resource.content}
                        </div>
                    )}
                </div>

                {/* Expand toggle */}
                {resource.content.length > 200 && (
                    <button
                        onClick={() => setIsExpanded(!isExpanded)}
                        className="mt-2 text-xs text-[var(--accent-primary)] hover:text-[var(--accent-hover)] inline-flex items-center gap-1"
                    >
                        {isExpanded ? (
                            <>
                                Show less <ChevronUp className="w-3 h-3" />
                            </>
                        ) : (
                            <>
                                Show more <ChevronDown className="w-3 h-3" />
                            </>
                        )}
                    </button>
                )}
            </GlassCard>

            {/* Full View Modal */}
            {showFullView && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
                    {/* Backdrop */}
                    <div
                        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
                        onClick={() => setShowFullView(false)}
                    />

                    {/* Modal Content */}
                    <div className="relative w-full max-w-4xl max-h-[90vh] bg-[var(--bg-base)] rounded-lg shadow-2xl flex flex-col">
                        {/* Header */}
                        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--glass-border)]">
                            <div className="flex-1 min-w-0">
                                <h2 className="text-lg font-semibold text-[var(--text-primary)] truncate">
                                    {resource.title || 'Untitled Resource'}
                                </h2>
                                <p className="text-sm text-[var(--text-tertiary)] mt-1">
                                    {resource.uploader_name} · {timeAgo(resource.created_at)}
                                </p>
                            </div>
                            <button
                                onClick={() => setShowFullView(false)}
                                className="ml-4 w-8 h-8 rounded-lg hover:bg-[var(--bg-sunken)] flex items-center justify-center text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors shrink-0"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        {/* Content */}
                        <div className="flex-1 overflow-y-auto px-6 py-6">
                            <MarkdownRenderer content={resource.content} />
                        </div>

                        {/* Footer with actions */}
                        {resource.file_url && (
                            <div className="px-6 py-4 border-t border-[var(--glass-border)] flex justify-end">
                                <a
                                    href={resource.file_url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="px-4 py-2 bg-[var(--accent-primary)] hover:bg-[var(--accent-hover)] text-white rounded-lg text-sm font-medium transition-colors"
                                >
                                    Open Original File
                                </a>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </>
    );
}
