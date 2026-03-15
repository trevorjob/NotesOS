'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { TabBar } from '@/components/ui/TabBar';
import { TopicWeekCard } from '@/components/cards/TopicWeekCard';
import { LinearProgressBar } from '@/components/data-display/LinearProgressBar';
import { EmptyState } from '@/components/feedback/EmptyState';
import { Skeleton, SkeletonCard } from '@/components/feedback/Skeleton';
import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { FAB } from '@/components/ui/FAB';
import { CreateEditTopicModal } from '@/components/modals/CreateEditTopicModal';
import { useCourseStore } from '@/stores/courses';
import { api } from '@/lib/api';

const TABS = [{ id: 'syllabus', label: 'Syllabus' }, { id: 'progress', label: 'Progress' }];

export default function CourseSyllabusPage() {
  const { courseId } = useParams<{ courseId: string }>();
  const router = useRouter();

  const { currentCourse, isLoading, selectCourse, createTopic, updateTopic, deleteTopic } = useCourseStore();
  const [tab, setTab] = useState('syllabus');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingTopic, setEditingTopic] = useState<any>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => { selectCourse(courseId); }, [courseId, selectCourse]);

  const handleSave = async (data: { title: string; description?: string; weekNumber?: number }) => {
    setSaving(true);
    try {
      if (editingTopic) {
        await updateTopic(courseId, editingTopic.id, { title: data.title, description: data.description, week_number: data.weekNumber });
      } else {
        const nextIdx = currentCourse?.topics?.length ?? 0;
        await createTopic(courseId, { title: data.title, description: data.description, week_number: data.weekNumber, order_index: nextIdx });
      }
    } finally {
      setSaving(false);
      setEditingTopic(null);
    }
  };

  const handleDelete = async (id: string) => {
    if (!currentCourse) return;
    await deleteTopic(courseId, id);
  };

  if (isLoading || !currentCourse) {
    return (
      <div className="px-4 md:px-8 py-6 max-w-4xl mx-auto">
        <Skeleton className="h-7 w-48 mb-1" variant="text" />
        <Skeleton className="h-4 w-24 mb-6" variant="text" />
        <div className="flex flex-col gap-3">
          {[...Array(4)].map((_, i) => <SkeletonCard key={i} />)}
        </div>
      </div>
    );
  }

  const topics = currentCourse.topics ?? [];
  const completionPct = topics.length > 0
    ? Math.round(topics.filter((t: any) => (t.mastery_level ?? 0) >= 70).length / topics.length * 100)
    : 0;

  return (
    <div className="px-4 md:px-8 py-6 max-w-4xl mx-auto">
      {/* Course header */}
      <div className="mb-6">
        <button
          onClick={() => router.push('/courses')}
          className="flex items-center gap-1.5 text-xs uppercase tracking-wider font-bold text-[var(--color-primary)] hover:underline mb-2"
        >
          <Icon name="arrow_back" size="xs" /> Courses
        </button>
        <h1 className="font-display font-bold text-2xl text-[var(--text-primary)] mb-0.5">
          {currentCourse.name}
        </h1>
        <p className="text-xs font-bold uppercase tracking-widest text-[var(--text-secondary)] mb-3">
          {currentCourse.code}
        </p>
        <LinearProgressBar value={completionPct} showLabel className="max-w-xs" />
      </div>

      {/* Tabs */}
      <TabBar tabs={TABS} active={tab} onChange={(id) => id === 'progress' ? router.push(`/courses/${courseId}/progress`) : setTab(id)} className="mb-6" />

      {/* Topic list */}
      {topics.length === 0 ? (
        <EmptyState
          icon="topic"
          title="No topics yet"
          body="Create your first topic to start organizing your study materials."
          ctaLabel="Create Topic"
          onCta={() => { setEditingTopic(null); setModalOpen(true); }}
        />
      ) : (
        <div className="flex flex-col gap-3">
          {topics.map((t: any) => {
            const mastery = t.mastery_level ?? 0;
            const status = mastery >= 70 ? 'completed' : mastery > 0 ? 'active' : 'not_started';
            return (
              <TopicWeekCard
                key={t.id}
                id={t.id}
                courseId={courseId}
                title={t.title}
                weekNumber={t.week_number}
                status={status}
                completionPercentage={Math.round(mastery)}
                resourceCount={t.resource_count}
                onEdit={(id) => { setEditingTopic(topics.find((tp: any) => tp.id === id)); setModalOpen(true); }}
                onDelete={handleDelete}
              />
            );
          })}
        </div>
      )}

      {/* FAB to add topics */}
      {topics.length > 0 && (
        <FAB
          icon="add"
          label="New Topic"
          onClick={() => { setEditingTopic(null); setModalOpen(true); }}
        />
      )}

      {/* Create/Edit Modal */}
      <CreateEditTopicModal
        open={modalOpen}
        onClose={() => { setModalOpen(false); setEditingTopic(null); }}
        onSave={handleSave}
        onDelete={editingTopic ? handleDelete : undefined}
        editingTopic={editingTopic ? {
          id: editingTopic.id,
          title: editingTopic.title,
          description: editingTopic.description,
          weekNumber: editingTopic.week_number,
        } : null}
        loading={saving}
      />
    </div>
  );
}
