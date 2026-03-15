'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { TabBar } from '@/components/ui/TabBar';
import { CourseCard } from '@/components/cards/CourseCard';
import { InviteCodeBlock } from '@/components/feedback/InviteCodeBlock';
import { Avatar } from '@/components/data-display/Avatar';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Skeleton } from '@/components/feedback/Skeleton';
import { Button } from '@/components/ui/Button';
import { StatusBadge } from '@/components/feedback/StatusBadge';
import { Icon } from '@/components/ui/Icon';
import { Modal } from '@/components/feedback/Modal';
import { apiClient } from '@/lib/api';
import { useAuthStore } from '@/stores/auth';

interface SemesterDetail {
  id: string;
  name: string;
  owner_id: string;
  invite_code: string;
  start_date?: string;
  end_date?: string;
  courses: Array<{ id: string; code: string; name: string; completion_percentage?: number; last_studied?: string | null }>;
  members: Array<{ user_id: string; full_name: string; role: string; joined_at: string }>;
}

const TABS = [{ id: 'courses', label: 'Courses' }, { id: 'members', label: 'Members' }];

export default function SemesterDetailPage() {
  const { semesterId } = useParams<{ semesterId: string }>();
  const router         = useRouter();
  const user           = useAuthStore((s) => s.user);

  const [data, setData]       = useState<SemesterDetail | null>(null);
  const [tab, setTab]         = useState('courses');
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');
  const [leaveModal, setLeave]  = useState(false);
  const [deleteModal, setDelete] = useState(false);
  const [acting, setActing]     = useState(false);

  useEffect(() => {
    apiClient.get(`/api/semesters/${semesterId}`)
      .then((r) => setData(r.data))
      .catch(() => setError('Failed to load semester.'))
      .finally(() => setLoading(false));
  }, [semesterId]);

  const isOwner = data?.owner_id === user?.id;

  const handleLeave = async () => {
    setActing(true);
    try {
      await apiClient.delete(`/api/semesters/${semesterId}/leave`);
      router.push('/courses');
    } catch {} finally { setActing(false); }
  };

  const handleDelete = async () => {
    setActing(true);
    try {
      await apiClient.delete(`/api/semesters/${semesterId}`);
      router.push('/courses');
    } catch {} finally { setActing(false); }
  };

  if (loading) {
    return (
      <div className="px-4 md:px-8 py-6 max-w-4xl mx-auto">
        <Skeleton className="h-7 w-48 mb-2" variant="text" />
        <Skeleton className="h-4 w-64 mb-8" variant="text" />
        <Skeleton className="h-14 w-full mb-6" />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-32" />)}
        </div>
      </div>
    );
  }

  if (error || !data) {
    return <EmptyState icon="error_outline" title="Something went wrong" body={error} ctaLabel="Go back" onCta={() => router.back()} />;
  }

  return (
    <div className="px-4 md:px-8 py-6 max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Icon name="folder" size="sm" className="text-[var(--color-primary)]" filled />
            <h1 className="font-display font-bold text-xl text-[var(--text-primary)] truncate">
              {data.name}
            </h1>
          </div>
          {(data.start_date || data.end_date) && (
            <p className="text-xs text-[var(--text-tertiary)]">
              {data.start_date && new Date(data.start_date).toLocaleDateString(undefined, { month: 'short', year: 'numeric' })}
              {data.start_date && data.end_date && ' – '}
              {data.end_date && new Date(data.end_date).toLocaleDateString(undefined, { month: 'short', year: 'numeric' })}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          {isOwner ? (
            <Button variant="danger" size="sm" onClick={() => setDelete(true)}>Delete</Button>
          ) : (
            <Button variant="ghost" size="sm" onClick={() => setLeave(true)}>Leave</Button>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="flex items-center gap-4 mb-6 text-xs text-[var(--text-tertiary)]">
        <span className="flex items-center gap-1"><Icon name="school" size="xs" />{data.courses.length} courses</span>
        <span className="flex items-center gap-1"><Icon name="group" size="xs" />{data.members.length} members</span>
        {isOwner && <StatusBadge variant="primary" label="Owner" />}
      </div>

      {/* Invite code (owner only) */}
      {isOwner && (
        <div className="mb-6">
          <p className="text-xs uppercase tracking-wider font-bold text-[var(--text-tertiary)] mb-2">Invite Code</p>
          <InviteCodeBlock code={data.invite_code} />
        </div>
      )}

      {/* Tabs */}
      <TabBar tabs={TABS} active={tab} onChange={setTab} className="mb-5" />

      {tab === 'courses' && (
        data.courses.length === 0 ? (
          <EmptyState
            icon="school"
            title="No courses yet"
            body={isOwner ? 'Add courses to this semester from the course page.' : 'The owner has not added any courses yet.'}
          />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {data.courses.map((c) => (
              <CourseCard
                key={c.id}
                id={c.id}
                code={c.code}
                name={c.name}
                completionPercentage={c.completion_percentage}
                lastStudied={c.last_studied}
              />
            ))}
          </div>
        )
      )}

      {tab === 'members' && (
        <div className="flex flex-col gap-3">
          {data.members.map((m) => (
            <div key={m.user_id} className="flex items-center gap-3 p-4 rounded-xl border border-[var(--border-base)] bg-[var(--bg-elevated)]">
              <Avatar name={m.full_name} size="sm" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-[var(--text-primary)]">{m.full_name}</p>
                <p className="text-xs text-[var(--text-tertiary)]">
                  Joined {new Date(m.joined_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                </p>
              </div>
              {m.role === 'OWNER' && <StatusBadge variant="primary" label="Owner" />}
            </div>
          ))}
        </div>
      )}

      {/* Modals */}
      <Modal open={leaveModal} onClose={() => setLeave(false)} title="Leave semester?" variant="destructive" confirmLabel="Leave" onConfirm={handleLeave} loading={acting}>
        You will lose access to all courses in this semester.
      </Modal>
      <Modal open={deleteModal} onClose={() => setDelete(false)} title="Delete semester?" variant="destructive" confirmLabel="Delete" onConfirm={handleDelete} loading={acting}>
        This will permanently delete <strong>{data.name}</strong>. Courses will not be deleted.
      </Modal>
    </div>
  );
}
