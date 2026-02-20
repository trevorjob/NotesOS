/**
 * Resource Card Component
 * Glass card displaying a resource with markdown rendering, metadata, OCR status, verification badge, fact-checks, and original file viewing
 */

'use client';

import { useState, useEffect } from 'react';
import { FileText, Image, File, Check, AlertTriangle, Trash2, ChevronDown, ChevronUp, Eye, X, ExternalLink, Loader2 } from 'lucide-react';
import { GlassCard } from './ui';
import { MarkdownRenderer } from './MarkdownRenderer';

interface ResourceFile {
    id: string;
    file_url: string;
    file_name?: string;
    file_order: number;
    ocr_confidence?: number;
}

interface FactCheck {
    id: string;
    claim_text: string;
    verification_status: string;
    confidence_score: number;
    ai_explanation: string;
    sources: any[];
    created_at: string;
}

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
        files?: ResourceFile[];
        processing_status?: 'processing' | 'completed' | 'failed'; // From WebSocket
    };
    currentUserId?: string;
    onDelete?: (id: string) => void;
    onFactCheck?: (id: string) => void;
    onUpdate?: (id: string, data: Partial<{ title: string }>) => void;
    onReprocess?: (id: string) => void;
    factChecks?: FactCheck[];
    isLoadingFactChecks?: boolean;
}

export function ResourceCard({
    resource,
    currentUserId,
    onDelete,
    onFactCheck,
    onUpdate,
    onReprocess,
    factChecks = [],
    isLoadingFactChecks = false
}: ResourceCardProps) {
    const [isExpanded, setIsExpanded] = useState(false);
    const [showFullView, setShowFullView] = useState(false);
    const [showFactChecks, setShowFactChecks] = useState(false);
    const [activeTab, setActiveTab] = useState<'content' | 'original'>('content');
    const [isEditing, setIsEditing] = useState(false);
    const [editTitle, setEditTitle] = useState(resource.title || '');
    const [isSaving, setIsSaving] = useState(false);

    const timeAgo = (date: string) => {
        const seconds = Math.floor((Date.now() - new Date(date).getTime()) / 1000);
        if (seconds < 60) return 'just now';
        if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
        return `${Math.floor(seconds / 86400)}d ago`;
    };

    const getTypeIcon = () => {
        switch (resource.resource_type.toLowerCase()) {
            case 'pdf':
                return <FileText className="w-4 h-4" />;
            case 'image':
                return <Image className="w-4 h-4" />;
            default:
                return <File className="w-4 h-4" />;
        }
    };

    const canDelete = currentUserId === resource.uploaded_by;
    const hasOriginalFiles = resource.file_url || (resource.files && resource.files.length > 0);

    const getStatusColor = (status: string) => {
        switch (status.toLowerCase()) {
            case 'verified':
                return 'text-[var(--success)] bg-[var(--success)]/10';
            case 'disputed':
            case 'unverified':
                return 'text-[var(--error)] bg-[var(--error)]/10';
            default:
                return 'text-[var(--text-tertiary)] bg-[var(--bg-sunken)]';
        }
    };

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
                                disabled={isLoadingFactChecks}
                                className="text-xs px-2 py-1 rounded text-[var(--text-secondary)] hover:bg-[var(--bg-sunken)] transition-colors disabled:opacity-50"
                                title="Verify with AI"
                            >
                                {isLoadingFactChecks ? 'Checking...' : 'Verify'}
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
                        {canDelete && onUpdate && (
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    setIsEditing(true);
                                    setEditTitle(resource.title || '');
                                }}
                                className="text-xs px-2 py-1 rounded text-[var(--text-secondary)] hover:bg-[var(--bg-sunken)] transition-colors"
                                title="Edit title"
                            >
                                Edit
                            </button>
                        )}
                    </div>
                </div>

                {isEditing && onUpdate && (
                    <div className="mb-3 space-y-2">
                        <input
                            type="text"
                            value={editTitle}
                            onChange={(e) => setEditTitle(e.target.value)}
                            placeholder="Title"
                            className="w-full px-3 py-2 bg-[var(--bg-sunken)] border border-[var(--glass-border)] rounded text-xs text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
                        />
                        <div className="flex gap-2 justify-end">
                            <button
                                type="button"
                                onClick={() => setIsEditing(false)}
                                className="px-3 py-1 rounded text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-sunken)] transition-colors"
                            >
                                Cancel
                            </button>
                            <button
                                type="button"
                                onClick={async () => {
                                    if (!editTitle.trim()) return;
                                    setIsSaving(true);
                                    try {
                                        await Promise.resolve(
                                            onUpdate(resource.id, {
                                                title: editTitle.trim(),
                                            })
                                        );
                                        setIsEditing(false);
                                    } finally {
                                        setIsSaving(false);
                                    }
                                }}
                                className="px-3 py-1 rounded text-xs bg-[var(--accent-primary)] text-white hover:bg-[var(--accent-hover)] transition-colors disabled:opacity-50"
                                disabled={isSaving || !editTitle.trim()}
                            >
                                {isSaving ? 'Saving...' : 'Save'}
                            </button>
                        </div>
                    </div>
                )}

                {/* Badges */}
                <div className="flex flex-wrap items-center gap-2 mb-3">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[var(--bg-sunken)] text-[var(--text-secondary)] text-xs">
                        {getTypeIcon()}
                        {resource.resource_type}
                    </span>

                    {resource.resource_type.toLowerCase() !== 'text' && (
                        <span className={`text-xs px-2 py-0.5 rounded-full inline-flex items-center gap-1 ${resource.processing_status === 'processing' || (!resource.is_processed && !resource.processing_status)
                                ? 'bg-[var(--accent-primary)]/10 text-[var(--accent-primary)]'
                                : resource.processing_status === 'failed'
                                    ? 'bg-[var(--error)]/10 text-[var(--error)]'
                                    : resource.is_processed || resource.processing_status === 'completed'
                                        ? 'bg-[var(--success)]/10 text-[var(--success)]'
                                        : 'bg-[var(--bg-sunken)] text-[var(--text-tertiary)]'
                            }`}>
                            {(resource.processing_status === 'processing' || (!resource.is_processed && !resource.processing_status)) && (
                                <Loader2 className="w-3 h-3 animate-spin" />
                            )}
                            {resource.processing_status === 'failed'
                                ? 'Processing failed'
                                : resource.processing_status === 'processing' || (!resource.is_processed && !resource.processing_status)
                                    ? 'Processing...'
                                    : 'Processed'}
                        </span>
                    )}

                    {onReprocess && resource.resource_type.toLowerCase() !== 'text' && resource.ocr_confidence !== undefined && resource.ocr_confidence < 0.8 && (
                        <button
                            type="button"
                            onClick={() => onReprocess(resource.id)}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[var(--bg-sunken)] text-[var(--text-secondary)] text-xs hover:text-[var(--text-primary)] hover:bg-[var(--bg-sunken)]/80 transition-colors"
                        >
                            Reprocess OCR
                        </button>
                    )}

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

                    {factChecks.length > 0 && (
                        <button
                            onClick={() => setShowFactChecks(!showFactChecks)}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] text-xs hover:bg-[var(--accent-primary)]/20 transition-colors"
                        >
                            {factChecks.filter(fc => fc.verification_status === 'verified').length}/{factChecks.length} verified
                            {showFactChecks ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                        </button>
                    )}
                </div>

                {/* Fact Checks Results */}
                {showFactChecks && factChecks.length > 0 && (
                    <div className="mb-3 p-3 bg-[var(--bg-sunken)] rounded-lg space-y-2">
                        <h4 className="text-xs font-medium text-[var(--text-primary)] mb-2">Fact Check Results</h4>
                        {factChecks.map((fc, idx) => (
                            <div key={fc.id} className="text-xs space-y-1">
                                <div className="flex items-start gap-2">
                                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${getStatusColor(fc.verification_status)}`}>
                                        {fc.verification_status}
                                    </span>
                                    <span className="flex-1 text-[var(--text-secondary)]">{fc.claim_text}</span>
                                </div>
                                {fc.ai_explanation && (
                                    <p className="text-[var(--text-tertiary)] pl-2 border-l-2 border-[var(--glass-border)]">
                                        {fc.ai_explanation}
                                    </p>
                                )}
                                {fc.confidence_score && (
                                    <div className="flex items-center gap-2 pl-2">
                                        <span className="text-[var(--text-tertiary)]">Confidence:</span>
                                        <div className="flex-1 h-1.5 bg-[var(--bg-base)] rounded-full overflow-hidden">
                                            <div
                                                className="h-full bg-[var(--accent-primary)]"
                                                style={{ width: `${fc.confidence_score * 100}%` }}
                                            />
                                        </div>
                                        <span className="text-[var(--text-tertiary)]">{Math.round(fc.confidence_score * 100)}%</span>
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                )}

                {/* Content preview */}
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
                    <div
                        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
                        onClick={() => setShowFullView(false)}
                    />

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

                        {/* Tabs if original files exist */}
                        {hasOriginalFiles && (
                            <div className="flex border-b border-[var(--glass-border)] px-6">
                                <button
                                    onClick={() => setActiveTab('content')}
                                    className={`px-4 py-2 text-sm font-medium transition-colors ${activeTab === 'content'
                                        ? 'text-[var(--accent-primary)] border-b-2 border-[var(--accent-primary)]'
                                        : 'text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]'
                                        }`}
                                >
                                    Extracted Text
                                </button>
                                <button
                                    onClick={() => setActiveTab('original')}
                                    className={`px-4 py-2 text-sm font-medium transition-colors ${activeTab === 'original'
                                        ? 'text-[var(--accent-primary)] border-b-2 border-[var(--accent-primary)]'
                                        : 'text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]'
                                        }`}
                                >
                                    Original File
                                </button>
                            </div>
                        )}

                        {/* Content */}
                        <div className="flex-1 overflow-y-auto px-6 py-6">
                            {activeTab === 'content' ? (
                                <MarkdownRenderer content={resource.content} />
                            ) : (
                                <div className="space-y-4">
                                    {resource.resource_type.toLowerCase() === 'image' && resource.files && resource.files.length > 0 ? (
                                        <>
                                            <p className="text-sm text-[var(--text-tertiary)] mb-4">Original images ({resource.files.length})</p>
                                            <div className="space-y-4">
                                                {resource.files
                                                    .sort((a, b) => a.file_order - b.file_order)
                                                    .map((file, idx) => (
                                                        <div key={file.id} className="border border-[var(--glass-border)] rounded-lg overflow-hidden">
                                                            <img
                                                                src={file.file_url}
                                                                alt={file.file_name || `Page ${idx + 1}`}
                                                                className="w-full"
                                                            />
                                                            {file.file_name && (
                                                                <div className="px-3 py-2 bg-[var(--bg-sunken)] text-xs text-[var(--text-secondary)]">
                                                                    {file.file_name}
                                                                </div>
                                                            )}
                                                        </div>
                                                    ))}
                                            </div>
                                        </>
                                    ) : resource.file_url ? (
                                        <div className="text-center py-8">
                                            <a
                                                href={resource.file_url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="inline-flex items-center gap-2 px-4 py-2 bg-[var(--accent-primary)] hover:bg-[var(--accent-hover)] text-white rounded-lg text-sm font-medium transition-colors"
                                            >
                                                <ExternalLink className="w-4 h-4" />
                                                Open {resource.resource_type.toUpperCase()} in new tab
                                            </a>
                                        </div>
                                    ) : (
                                        <p className="text-sm text-[var(--text-tertiary)] text-center py-8">No original file available</p>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
