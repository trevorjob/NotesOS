/**
 * Resource Card Component
 * Glass card displaying a resource with markdown rendering, metadata, OCR status,
 * verification status, per-claim fact-check results, and original file viewing.
 */

'use client';

import { useState, useEffect, useRef } from 'react';
import {
    FileText, Image, File, Check, AlertTriangle, Trash2,
    ChevronDown, ChevronUp, Eye, X, ExternalLink, Loader2,
    ShieldCheck, ShieldAlert, Shield, ChevronRight,
} from 'lucide-react';
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
        processing_status?: 'processing' | 'completed' | 'failed';
    };
    currentUserId?: string;
    onDelete?: (id: string) => void;
    onFactCheck?: (id: string) => void;
    onUpdate?: (id: string, data: Partial<{ title: string }>) => void;
    onReprocess?: (id: string) => void;
    factChecks?: FactCheck[];
    isLoadingFactChecks?: boolean;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function timeAgo(date: string): string {
    const seconds = Math.floor((Date.now() - new Date(date).getTime()) / 1000);
    if (seconds < 60) return 'just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
}

function claimStatusMeta(status: string): {
    icon: React.ReactNode;
    label: string;
    color: string;
} {
    switch (status.toLowerCase()) {
        case 'verified':
            return {
                icon: <Check className="w-3.5 h-3.5" />,
                label: 'Verified',
                color: 'text-[var(--success)]',
            };
        case 'disputed':
        case 'false':
            return {
                icon: <X className="w-3.5 h-3.5" />,
                label: 'Disputed',
                color: 'text-[var(--error)]',
            };
        default:
            return {
                icon: <AlertTriangle className="w-3.5 h-3.5" />,
                label: 'Unverified',
                color: 'text-[#A07830]',
            };
    }
}

// ── Sub-components ────────────────────────────────────────────────────────────

function ClaimRow({ fc }: { fc: FactCheck }) {
    const [expanded, setExpanded] = useState(false);
    const { icon, label, color } = claimStatusMeta(fc.verification_status);

    return (
        <div className="group">
            {/* Summary row */}
            <button
                onClick={() => setExpanded(!expanded)}
                className="w-full flex items-start gap-3 py-2.5 px-3 rounded-lg hover:bg-[var(--bg-sunken)] transition-colors text-left"
            >
                {/* Status icon */}
                <span className={`mt-0.5 shrink-0 ${color}`}>{icon}</span>

                {/* Claim text */}
                <span className="flex-1 text-sm text-[var(--text-secondary)] leading-snug line-clamp-2">
                    {fc.claim_text}
                </span>

                {/* Confidence + chevron */}
                <span className="shrink-0 flex items-center gap-2 ml-2">
                    <span className="text-xs text-[var(--text-tertiary)] font-mono">
                        {Math.round(fc.confidence_score * 100)}%
                    </span>
                    <ChevronRight
                        className={`w-3.5 h-3.5 text-[var(--text-tertiary)] transition-transform duration-150 ${expanded ? 'rotate-90' : ''}`}
                    />
                </span>
            </button>

            {/* Expanded detail */}
            {expanded && (
                <div className="mx-3 mb-2 pl-6 pr-3 space-y-2">
                    {fc.ai_explanation && (
                        <p className="text-sm text-[var(--text-tertiary)] leading-relaxed border-l-2 border-[var(--glass-border)] pl-3">
                            {fc.ai_explanation}
                        </p>
                    )}
                    {fc.sources && fc.sources.length > 0 && (
                        <div className="space-y-1">
                            {fc.sources.map((src: any, i: number) => (
                                <a
                                    key={i}
                                    href={src.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="flex items-center gap-1.5 text-xs text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors"
                                >
                                    <ExternalLink className="w-3 h-3 shrink-0" />
                                    {src.title || src.url}
                                </a>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}

// ── Verification status area ──────────────────────────────────────────────────

interface VerificationAreaProps {
    resource: ResourceCardProps['resource'];
    factChecks: FactCheck[];
    isLoadingFactChecks: boolean;
    isFactChecking: boolean;
    onFactCheck?: (id: string) => void;
}

function VerificationArea({
    resource,
    factChecks,
    isLoadingFactChecks,
    isFactChecking,
    onFactCheck,
}: VerificationAreaProps) {
    const [claimsExpanded, setClaimsExpanded] = useState(false);

    const verifiedCount = factChecks.filter(
        (fc) => fc.verification_status.toLowerCase() === 'verified'
    ).length;
    const total = factChecks.length;
    const hasIssues = total > 0 && verifiedCount < total;
    const allVerified = total > 0 && verifiedCount === total;

    // ── Checking… ──
    if (isFactChecking || isLoadingFactChecks) {
        return (
            <div className="flex items-center gap-2 mt-3 pt-3 border-t border-[var(--glass-border)]">
                <Loader2 className="w-3.5 h-3.5 animate-spin text-[var(--text-tertiary)]" />
                <span className="text-xs text-[var(--text-tertiary)]">Fact-checking…</span>
            </div>
        );
    }

    // ── Has results ──
    if (total > 0) {
        return (
            <div className="mt-3 pt-3 border-t border-[var(--glass-border)]">
                {/* Status badge + toggle */}
                <button
                    onClick={() => setClaimsExpanded(!claimsExpanded)}
                    className="w-full flex items-center gap-2 hover:opacity-80 transition-opacity"
                >
                    {allVerified ? (
                        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#6B8F71]/10 text-[#6B8F71] text-xs font-medium">
                            <ShieldCheck className="w-3.5 h-3.5" />
                            Verified
                        </span>
                    ) : (
                        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#D4A853]/10 text-[#A07830] text-xs font-medium">
                            <ShieldAlert className="w-3.5 h-3.5" />
                            {hasIssues ? 'Issues found' : 'Partially verified'}
                        </span>
                    )}
                    <span className="text-xs text-[var(--text-tertiary)]">
                        {verifiedCount}/{total} claims verified
                    </span>
                    <span className="ml-auto">
                        {claimsExpanded
                            ? <ChevronUp className="w-3.5 h-3.5 text-[var(--text-tertiary)]" />
                            : <ChevronDown className="w-3.5 h-3.5 text-[var(--text-tertiary)]" />
                        }
                    </span>
                </button>

                {/* Claims list */}
                {claimsExpanded && (
                    <div className="mt-2 -mx-1 divide-y divide-[var(--glass-border)]">
                        {factChecks.map((fc) => (
                            <ClaimRow key={fc.id} fc={fc} />
                        ))}
                    </div>
                )}
            </div>
        );
    }

    // ── Not verified ──
    if (!resource.is_verified && onFactCheck) {
        return (
            <div className="flex items-center gap-3 mt-3 pt-3 border-t border-[var(--glass-border)]">
                <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[var(--bg-sunken)] text-[var(--text-tertiary)] text-xs">
                    <Shield className="w-3.5 h-3.5" />
                    Not verified
                </span>
                <button
                    onClick={() => onFactCheck(resource.id)}
                    className="text-xs px-3 py-1 rounded-lg border border-[#D6D3D1] text-[var(--text-secondary)] hover:bg-[var(--bg-sunken)] hover:border-[var(--text-tertiary)] transition-colors font-medium"
                >
                    Verify with AI
                </button>
            </div>
        );
    }

    return null;
}

// ── Main component ────────────────────────────────────────────────────────────

export function ResourceCard({
    resource,
    currentUserId,
    onDelete,
    onFactCheck,
    onUpdate,
    onReprocess,
    factChecks = [],
    isLoadingFactChecks = false,
}: ResourceCardProps) {
    const [isExpanded, setIsExpanded] = useState(false);
    const [showFullView, setShowFullView] = useState(false);
    const [activeTab, setActiveTab] = useState<'content' | 'original'>('content');
    const [isEditing, setIsEditing] = useState(false);
    const [editTitle, setEditTitle] = useState(resource.title || '');
    const [isSaving, setIsSaving] = useState(false);

    // Local "checking" state: true from when Verify is clicked until WS delivers results
    const [isFactChecking, setIsFactChecking] = useState(false);
    const prevFactCheckCount = useRef(factChecks.length);

    useEffect(() => {
        // Once fact-checks arrive (count goes from 0 → N), clear local checking flag
        if (factChecks.length > prevFactCheckCount.current) {
            setIsFactChecking(false);
        }
        prevFactCheckCount.current = factChecks.length;
    }, [factChecks.length]);

    const handleVerify = () => {
        if (!onFactCheck) return;
        setIsFactChecking(true);
        onFactCheck(resource.id);
    };

    const getTypeIcon = () => {
        switch (resource.resource_type.toLowerCase()) {
            case 'pdf': return <FileText className="w-4 h-4" />;
            case 'image': return <Image className="w-4 h-4" />;
            default: return <File className="w-4 h-4" />;
        }
    };

    const canDelete = currentUserId === resource.uploaded_by;
    const hasOriginalFiles = resource.file_url || (resource.files && resource.files.length > 0);

    return (
        <>
            <GlassCard className="p-4 hover:border-[#C4BAB0] transition-colors duration-200">
                {/* ── Header ───────────────────────────────────────────── */}
                <div className="flex items-start justify-between gap-3 mb-3">
                    <div className="flex-1 min-w-0">
                        {isEditing && onUpdate ? (
                            <div className="space-y-2">
                                <input
                                    type="text"
                                    value={editTitle}
                                    onChange={(e) => setEditTitle(e.target.value)}
                                    autoFocus
                                    placeholder="Title"
                                    className="w-full px-3 py-1.5 bg-[var(--bg-sunken)] border border-[var(--glass-border)] rounded-lg text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
                                />
                                <div className="flex gap-2">
                                    <button
                                        onClick={() => setIsEditing(false)}
                                        className="px-3 py-1 rounded-lg text-xs text-zinc-500 hover:bg-zinc-100 transition-colors"
                                    >
                                        Cancel
                                    </button>
                                    <button
                                        disabled={isSaving || !editTitle.trim()}
                                        onClick={async () => {
                                            if (!editTitle.trim()) return;
                                            setIsSaving(true);
                                            try {
                                                await Promise.resolve(onUpdate(resource.id, { title: editTitle.trim() }));
                                                setIsEditing(false);
                                            } finally {
                                                setIsSaving(false);
                                            }
                                        }}
                                        className="px-3 py-1 rounded-lg text-xs bg-[var(--accent-primary)] text-[var(--bg-elevated)] hover:bg-[var(--accent-hover)] transition-colors disabled:opacity-50"
                                    >
                                        {isSaving ? 'Saving…' : 'Save'}
                                    </button>
                                </div>
                            </div>
                        ) : (
                            <>
                                <h3 className="text-sm font-medium text-[var(--text-primary)] truncate leading-snug">
                                    {resource.title || 'Untitled Resource'}
                                </h3>
                                <p className="text-xs text-[var(--text-tertiary)] mt-0.5">
                                    {resource.uploader_name} · {timeAgo(resource.created_at)}
                                </p>
                            </>
                        )}
                    </div>

                    {/* Action buttons */}
                    {!isEditing && (
                        <div className="flex items-center gap-1 shrink-0">
                            <button
                                onClick={() => setShowFullView(true)}
                                title="View full resource"
                                className="p-1.5 rounded-lg text-[var(--text-tertiary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-sunken)] transition-colors"
                            >
                                <Eye className="w-4 h-4" />
                            </button>
                            {canDelete && onUpdate && (
                                <button
                                    onClick={() => { setIsEditing(true); setEditTitle(resource.title || ''); }}
                                    title="Edit title"
                                    className="p-1.5 rounded-lg text-[var(--text-tertiary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-sunken)] transition-colors text-xs font-medium"
                                >
                                    Edit
                                </button>
                            )}
                            {canDelete && onDelete && (
                                <button
                                    onClick={() => onDelete(resource.id)}
                                    title="Delete"
                                    className="p-1.5 rounded-lg text-[var(--text-tertiary)] hover:text-[var(--error)] hover:bg-[var(--error)]/10 transition-colors"
                                >
                                    <Trash2 className="w-4 h-4" />
                                </button>
                            )}
                        </div>
                    )}
                </div>

                {/* ── Metadata badges ───────────────────────────────────── */}
                <div className="flex flex-wrap items-center gap-2 mb-3">
                    {/* Type badge */}
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[var(--bg-sunken)] text-[var(--text-tertiary)] text-xs">
                        {getTypeIcon()}
                        {resource.resource_type}
                    </span>

                    {/* Processing status — only for non-text resources */}
                    {resource.resource_type.toLowerCase() !== 'text' && (
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs ${resource.processing_status === 'processing' || (!resource.is_processed && !resource.processing_status)
                            ? 'bg-[var(--bg-sunken)] text-[var(--text-tertiary)]'
                            : resource.processing_status === 'failed'
                                ? 'bg-[var(--error)]/10 text-[var(--error)]'
                                : 'bg-[#6B8F71]/10 text-[#6B8F71]'
                            }`}>
                            {(resource.processing_status === 'processing' || (!resource.is_processed && !resource.processing_status)) && (
                                <Loader2 className="w-3 h-3 animate-spin" />
                            )}
                            {resource.processing_status === 'failed'
                                ? 'Processing failed'
                                : resource.processing_status === 'processing' || (!resource.is_processed && !resource.processing_status)
                                    ? 'Processing…'
                                    : 'Processed'}
                        </span>
                    )}

                    {/* Low OCR confidence warning */}
                    {resource.ocr_confidence !== undefined && resource.ocr_confidence < 0.8 && (
                        <span
                            title={`OCR Confidence: ${Math.round(resource.ocr_confidence * 100)}%`}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[#D4A853]/10 text-[#A07830] text-xs"
                        >
                            <AlertTriangle className="w-3 h-3" />
                            Low confidence ({Math.round(resource.ocr_confidence * 100)}%)
                        </span>
                    )}

                    {/* Re-transcribe — image resources only, uploader only */}
                    {onReprocess && canDelete && resource.resource_type.toLowerCase() === 'image' && (
                        <button
                            onClick={() => onReprocess(resource.id)}
                            disabled={resource.processing_status === 'processing'}
                            title="Re-transcribe with GPT-4o Vision"
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[var(--bg-sunken)] text-[var(--text-tertiary)] text-xs hover:bg-[var(--bg-elevated)] hover:text-[var(--text-secondary)] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {resource.processing_status === 'processing' ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                            ) : null}
                            Re-transcribe
                        </button>
                    )}
                </div>

                {/* ── Content preview ───────────────────────────────────── */}
                <div className="text-sm">
                    {isExpanded ? (
                        <MarkdownRenderer content={resource.content} className="max-h-96 overflow-y-auto" />
                    ) : (
                        <p className="line-clamp-3 text-[var(--text-secondary)] leading-relaxed text-sm">
                            {resource.content}
                        </p>
                    )}
                </div>

                {resource.content.length > 200 && (
                    <button
                        onClick={() => setIsExpanded(!isExpanded)}
                        className="mt-2 text-xs text-[var(--text-tertiary)] hover:text-[var(--text-primary)] inline-flex items-center gap-1 transition-colors"
                    >
                        {isExpanded
                            ? <><ChevronUp className="w-3 h-3" /> Show less</>
                            : <><ChevronDown className="w-3 h-3" /> Show more</>
                        }
                    </button>
                )}

                {/* ── Verification area ─────────────────────────────────── */}
                <VerificationArea
                    resource={resource}
                    factChecks={factChecks}
                    isLoadingFactChecks={isLoadingFactChecks}
                    isFactChecking={isFactChecking}
                    onFactCheck={handleVerify}
                />
            </GlassCard>

            {/* ── Full view modal ───────────────────────────────────────── */}
            {showFullView && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
                    <div
                        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
                        onClick={() => setShowFullView(false)}
                    />

                    <div className="relative w-full max-w-4xl max-h-[90vh] bg-[var(--bg-elevated)] rounded-xl shadow-2xl flex flex-col">
                        {/* Header */}
                        <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--glass-border)]">
                            <div className="flex-1 min-w-0">
                                <h2 className="text-lg font-medium text-[var(--text-primary)] truncate">
                                    {resource.title || 'Untitled Resource'}
                                </h2>
                                <p className="text-sm text-[var(--text-tertiary)] mt-0.5">
                                    {resource.uploader_name} · {timeAgo(resource.created_at)}
                                </p>
                            </div>
                            <button
                                onClick={() => setShowFullView(false)}
                                className="ml-4 w-8 h-8 rounded-lg flex items-center justify-center text-[var(--text-tertiary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-sunken)] transition-colors shrink-0"
                            >
                                <X className="w-5 h-5" />
                            </button>
                        </div>

                        {/* Tabs */}
                        {hasOriginalFiles && (
                            <div className="flex border-b border-[var(--glass-border)] px-6">
                                {(['content', 'original'] as const).map((tab) => (
                                    <button
                                        key={tab}
                                        onClick={() => setActiveTab(tab)}
                                        className={`px-4 py-2.5 text-sm font-medium transition-colors ${activeTab === tab
                                            ? 'text-[var(--text-primary)] border-b-2 border-[var(--text-primary)]'
                                            : 'text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]'
                                            }`}
                                    >
                                        {tab === 'content' ? 'Extracted Text' : 'Original File'}
                                    </button>
                                ))}
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
                                            <p className="text-sm text-[var(--text-tertiary)] mb-4">
                                                Original images ({resource.files.length})
                                            </p>
                                            <div className="space-y-4">
                                                {resource.files
                                                    .sort((a, b) => a.file_order - b.file_order)
                                                    .map((file, idx) => (
                                                        <div key={file.id} className="border border-[var(--glass-border)] rounded-xl overflow-hidden">
                                                            <img
                                                                src={file.file_url}
                                                                alt={file.file_name || `Page ${idx + 1}`}
                                                                className="w-full"
                                                            />
                                                            {file.file_name && (
                                                                <div className="px-3 py-2 bg-[var(--bg-sunken)] text-xs text-[var(--text-tertiary)]">
                                                                    {file.file_name}
                                                                </div>
                                                            )}
                                                        </div>
                                                    ))}
                                            </div>
                                        </>
                                    ) : resource.file_url ? (
                                        <div className="text-center py-12">
                                            <a
                                                href={resource.file_url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="inline-flex items-center gap-2 px-5 py-2.5 bg-[var(--accent-primary)] text-[var(--bg-elevated)] rounded-lg text-sm font-medium hover:bg-[var(--accent-hover)] transition-colors"
                                            >
                                                <ExternalLink className="w-4 h-4" />
                                                Open {resource.resource_type.toUpperCase()} in new tab
                                            </a>
                                        </div>
                                    ) : (
                                        <p className="text-sm text-[var(--text-tertiary)] text-center py-12">
                                            No original file available
                                        </p>
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
