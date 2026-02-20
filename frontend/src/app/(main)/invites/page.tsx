/**
 * NotesOS - Invites Page
 * Create and manage global class invites
 */

'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, Plus, Users, Copy, CheckCircle, XCircle, Trash2, Eye } from 'lucide-react';
import { useAuthStore } from '@/stores/auth';
import { MainLayout } from '@/components/layout';
import { GlassCard, Button } from '@/components/ui';
import { api } from '@/lib/api';

interface ClassInvite {
    id: string;
    name: string | null;
    invite_code: string;
    is_active: boolean;
    classmate_count: number;
    created_at: string;
}

interface Classmate {
    id: string;
    user_id: string;
    user_name: string;
    user_email: string;
    joined_at: string;
}

export default function InvitesPage() {
    const router = useRouter();
    const { user } = useAuthStore();
    const [invites, setInvites] = useState<ClassInvite[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [showCreateForm, setShowCreateForm] = useState(false);
    const [className, setClassName] = useState('');
    const [isCreating, setIsCreating] = useState(false);
    const [expandedInviteId, setExpandedInviteId] = useState<string | null>(null);
    const [classmates, setClassmates] = useState<Record<string, Classmate[]>>({});
    const [copiedCode, setCopiedCode] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        loadInvites();
    }, []);

    const loadInvites = async () => {
        setIsLoading(true);
        try {
            const response = await api.invites.listMyInvites();
            setInvites(response.data || []);
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to load invites');
        } finally {
            setIsLoading(false);
        }
    };

    const loadClassmates = async (classId: string) => {
        if (classmates[classId]) return;
        try {
            const response = await api.invites.listClassmates(classId);
            setClassmates((prev) => ({ ...prev, [classId]: response.data || [] }));
        } catch (err) {
            console.error('Failed to load classmates:', err);
        }
    };

    const handleCreate = async () => {
        if (isCreating) return;
        setIsCreating(true);
        setError(null);
        try {
            await api.invites.createClass(className.trim() || undefined);
            setClassName('');
            setShowCreateForm(false);
            await loadInvites();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to create invite');
        } finally {
            setIsCreating(false);
        }
    };

    const handleDeactivate = async (classId: string) => {
        try {
            await api.invites.deactivateClass(classId);
            await loadInvites();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to deactivate invite');
        }
    };

    const handleDelete = async (classId: string) => {
        if (!confirm('Delete this invite? This cannot be undone.')) return;
        try {
            await api.invites.deleteClass(classId);
            await loadInvites();
        } catch (err: any) {
            setError(err.response?.data?.detail || 'Failed to delete invite');
        }
    };

    const copyInviteCode = (code: string) => {
        navigator.clipboard.writeText(code);
        setCopiedCode(code);
        setTimeout(() => setCopiedCode(null), 2000);
    };

    const copyInviteLink = (code: string) => {
        const link = `${window.location.origin}/courses/join?class=${code}`;
        navigator.clipboard.writeText(link);
        setCopiedCode(`link-${code}`);
        setTimeout(() => setCopiedCode(null), 2000);
    };

    const toggleClassmates = (inviteId: string) => {
        if (expandedInviteId === inviteId) {
            setExpandedInviteId(null);
        } else {
            setExpandedInviteId(inviteId);
            loadClassmates(inviteId);
        }
    };

    const formatDate = (iso: string) => {
        if (!iso) return '—';
        try {
            const d = new Date(iso);
            return d.toLocaleDateString(undefined, { dateStyle: 'short' });
        } catch {
            return iso;
        }
    };

    return (
        <MainLayout>
            <div className="max-w-4xl mx-auto px-8 md:px-20 py-12">
                <Link
                    href="/courses"
                    className="inline-flex items-center gap-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] mb-8 transition-colors"
                >
                    <ArrowLeft className="w-4 h-4" />
                    Back to courses
                </Link>

                <div className="flex items-center justify-between mb-8">
                    <div>
                        <h1 className="text-2xl font-semibold text-[var(--text-primary)] mb-2">Class Invites</h1>
                        <p className="text-sm text-[var(--text-tertiary)]">
                            Create invite links to share all your courses at once
                        </p>
                    </div>
                    <Button
                        variant="primary"
                        onClick={() => setShowCreateForm(!showCreateForm)}
                    >
                        <Plus className="w-4 h-4 mr-2" />
                        Create Invite
                    </Button>
                </div>

                {error && (
                    <div className="mb-6 px-4 py-3 bg-[var(--error)]/10 border border-[var(--error)]/20 rounded-lg">
                        <p className="text-sm text-[var(--error)]">{error}</p>
                    </div>
                )}

                {showCreateForm && (
                    <GlassCard className="mb-6 p-6">
                        <h2 className="text-lg font-medium text-[var(--text-primary)] mb-4">Create New Invite</h2>
                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-[var(--text-primary)] mb-2">
                                    Class Name (optional)
                                </label>
                                <input
                                    type="text"
                                    value={className}
                                    onChange={(e) => setClassName(e.target.value)}
                                    placeholder="e.g., Fall 2024 History Class"
                                    className="w-full px-4 py-2.5 bg-[var(--bg-sunken)] border border-[var(--glass-border)] rounded-lg text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
                                />
                            </div>
                            <div className="bg-[var(--bg-sunken)] p-4 rounded-lg">
                                <p className="text-sm text-[var(--text-secondary)]">
                                    Anyone who joins with this invite code will be automatically enrolled in{' '}
                                    <strong>all courses</strong> you're currently enrolled in.
                                </p>
                            </div>
                            <div className="flex gap-3">
                                <Button
                                    variant="primary"
                                    onClick={handleCreate}
                                    disabled={isCreating}
                                >
                                    {isCreating ? 'Creating...' : 'Create Invite'}
                                </Button>
                                <Button
                                    variant="secondary"
                                    onClick={() => {
                                        setShowCreateForm(false);
                                        setClassName('');
                                    }}
                                >
                                    Cancel
                                </Button>
                            </div>
                        </div>
                    </GlassCard>
                )}

                {isLoading ? (
                    <GlassCard className="p-12 text-center">
                        <p className="text-[var(--text-tertiary)]">Loading invites...</p>
                    </GlassCard>
                ) : invites.length === 0 ? (
                    <GlassCard className="p-12 text-center">
                        <p className="text-[var(--text-tertiary)] mb-4">No invites yet</p>
                        <Button variant="primary" onClick={() => setShowCreateForm(true)}>
                            <Plus className="w-4 h-4 mr-2" />
                            Create your first invite
                        </Button>
                    </GlassCard>
                ) : (
                    <div className="space-y-4">
                        {invites.map((invite) => (
                            <GlassCard key={invite.id} className="p-6">
                                <div className="flex items-start justify-between flex-wrap gap-4">
                                    <div className="flex-1">
                                        <div className="flex items-center gap-3 mb-2">
                                            <h3 className="text-lg font-medium text-[var(--text-primary)]">
                                                {invite.name || 'Unnamed Class'}
                                            </h3>
                                            {invite.is_active ? (
                                                <span className="flex items-center gap-1 text-xs text-[var(--success)]">
                                                    <CheckCircle className="w-4 h-4" />
                                                    Active
                                                </span>
                                            ) : (
                                                <span className="flex items-center gap-1 text-xs text-[var(--text-tertiary)]">
                                                    <XCircle className="w-4 h-4" />
                                                    Inactive
                                                </span>
                                            )}
                                        </div>
                                        <p className="text-sm text-[var(--text-tertiary)] mb-4">
                                            Created {formatDate(invite.created_at)} · {invite.classmate_count} {invite.classmate_count === 1 ? 'classmate' : 'classmates'}
                                        </p>
                                        <div className="flex items-center gap-2 flex-wrap">
                                            <div className="flex items-center gap-2 px-3 py-1.5 bg-[var(--bg-sunken)] rounded-lg">
                                                <code className="text-sm font-mono text-[var(--text-primary)]">
                                                    {invite.invite_code}
                                                </code>
                                                <button
                                                    onClick={() => copyInviteCode(invite.invite_code)}
                                                    className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors"
                                                >
                                                    {copiedCode === invite.invite_code ? (
                                                        <CheckCircle className="w-4 h-4" />
                                                    ) : (
                                                        <Copy className="w-4 h-4" />
                                                    )}
                                                </button>
                                            </div>
                                            <Button
                                                variant="secondary"
                                                size="sm"
                                                onClick={() => copyInviteLink(invite.invite_code)}
                                            >
                                                {copiedCode === `link-${invite.invite_code}` ? (
                                                    <>
                                                        <CheckCircle className="w-4 h-4 mr-2" />
                                                        Link copied!
                                                    </>
                                                ) : (
                                                    <>
                                                        <Copy className="w-4 h-4 mr-2" />
                                                        Copy link
                                                    </>
                                                )}
                                            </Button>
                                        </div>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <Button
                                            variant="secondary"
                                            size="sm"
                                            onClick={() => toggleClassmates(invite.id)}
                                        >
                                            <Users className="w-4 h-4 mr-2" />
                                            Classmates ({invite.classmate_count})
                                        </Button>
                                        {invite.is_active && (
                                            <Button
                                                variant="secondary"
                                                size="sm"
                                                onClick={() => handleDeactivate(invite.id)}
                                            >
                                                Deactivate
                                            </Button>
                                        )}
                                        <Button
                                            variant="secondary"
                                            size="sm"
                                            onClick={() => handleDelete(invite.id)}
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </Button>
                                    </div>
                                </div>
                                {expandedInviteId === invite.id && (
                                    <div className="mt-6 pt-6 border-t border-[var(--glass-border)]">
                                        {!classmates[invite.id] ? (
                                            <p className="text-sm text-[var(--text-tertiary)]">Loading classmates...</p>
                                        ) : classmates[invite.id].length === 0 ? (
                                            <p className="text-sm text-[var(--text-tertiary)]">No classmates yet.</p>
                                        ) : (
                                            <ul className="space-y-2">
                                                {classmates[invite.id].map((cm) => (
                                                    <li key={cm.id} className="flex items-center justify-between text-sm">
                                                        <div>
                                                            <p className="text-[var(--text-primary)]">{cm.user_name}</p>
                                                            <p className="text-xs text-[var(--text-tertiary)]">{cm.user_email}</p>
                                                        </div>
                                                        <span className="text-xs text-[var(--text-tertiary)]">
                                                            {formatDate(cm.joined_at)}
                                                        </span>
                                                    </li>
                                                ))}
                                            </ul>
                                        )}
                                    </div>
                                )}
                            </GlassCard>
                        ))}
                    </div>
                )}
            </div>
        </MainLayout>
    );
}
