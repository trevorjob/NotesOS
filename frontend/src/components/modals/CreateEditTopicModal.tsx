'use client';

import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import { TextInputUnderline } from '@/components/ui/TextInputUnderline';
import { Textarea } from '@/components/ui/Textarea';
import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { Modal } from '@/components/feedback/Modal';

interface TopicFormData {
  title: string;
  description: string;
  weekNumber: string;
}

interface CreateEditTopicModalProps {
  open: boolean;
  onClose: () => void;
  onSave: (data: { title: string; description?: string; weekNumber?: number }) => Promise<void>;
  onDelete?: (id: string) => Promise<void>;
  editingTopic?: { id: string; title: string; description?: string; weekNumber?: number } | null;
  loading?: boolean;
}

export function CreateEditTopicModal({
  open,
  onClose,
  onSave,
  onDelete,
  editingTopic,
  loading = false,
}: CreateEditTopicModalProps) {
  const isEdit = !!editingTopic;

  const [form, setForm] = useState<TopicFormData>({
    title: '',
    description: '',
    weekNumber: '',
  });
  const [errors, setErrors] = useState<Partial<Record<keyof TopicFormData, string>>>({});
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (open && editingTopic) {
      setForm({
        title:      editingTopic.title ?? '',
        description: editingTopic.description ?? '',
        weekNumber:  editingTopic.weekNumber != null ? String(editingTopic.weekNumber) : '',
      });
    } else if (open) {
      setForm({ title: '', description: '', weekNumber: '' });
    }
    setErrors({});
  }, [open, editingTopic]);

  const validate = (): boolean => {
    const errs: Partial<Record<keyof TopicFormData, string>> = {};
    if (!form.title.trim()) errs.title = 'Title is required';
    if (form.weekNumber && isNaN(Number(form.weekNumber))) errs.weekNumber = 'Must be a number';
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSave = async () => {
    if (!validate()) return;
    await onSave({
      title:       form.title.trim(),
      description: form.description.trim() || undefined,
      weekNumber:  form.weekNumber ? Number(form.weekNumber) : undefined,
    });
    onClose();
  };

  const handleDelete = async () => {
    if (!editingTopic || !onDelete) return;
    setDeleting(true);
    try {
      await onDelete(editingTopic.id);
      setDeleteConfirmOpen(false);
      onClose();
    } finally {
      setDeleting(false);
    }
  };

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[100] flex items-end md:items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="topic-modal-title"
    >
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      <div className="relative w-full max-w-md glass-card p-6 animate-scale-in">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h2 id="topic-modal-title" className="text-lg font-display font-semibold text-[var(--text-primary)]">
            {isEdit ? 'Edit Topic' : 'New Topic'}
          </h2>
          <button
            onClick={onClose}
            className="min-w-[36px] min-h-[36px] flex items-center justify-center text-[var(--text-tertiary)] hover:text-[var(--text-primary)] rounded-lg hover:bg-[var(--bg-sunken)] transition-colors"
            aria-label="Close"
          >
            <Icon name="close" size="sm" />
          </button>
        </div>

        {/* Form */}
        <div className="flex flex-col gap-5">
          <TextInputUnderline
            label="Topic title"
            value={form.title}
            onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))}
            error={errors.title}
            placeholder="e.g. Introduction to Neural Networks"
            size="lg"
            serif
          />
          <TextInputUnderline
            label="Week number (optional)"
            type="number"
            min={1}
            value={form.weekNumber}
            onChange={(e) => setForm((f) => ({ ...f, weekNumber: e.target.value }))}
            error={errors.weekNumber}
            placeholder="e.g. 3"
          />
          <Textarea
            label="Description (optional)"
            value={form.description}
            onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            placeholder="Brief overview of this topic…"
            rows={3}
          />
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3 mt-8">
          {isEdit && onDelete && (
            <button
              onClick={() => setDeleteConfirmOpen(true)}
              className="flex items-center gap-1.5 text-sm text-[var(--color-error)] hover:underline"
            >
              <Icon name="delete" size="xs" /> Delete
            </button>
          )}
          <div className="flex-1" />
          <Button variant="secondary" size="md" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button variant="primary" size="md" onClick={handleSave} loading={loading}>
            {isEdit ? 'Save changes' : 'Create topic'}
          </Button>
        </div>
      </div>

      {/* Nested delete confirmation */}
      <Modal
        open={deleteConfirmOpen}
        onClose={() => setDeleteConfirmOpen(false)}
        title="Delete topic?"
        variant="destructive"
        confirmLabel="Delete"
        onConfirm={handleDelete}
        loading={deleting}
      >
        <p>This will permanently delete <strong>{editingTopic?.title}</strong> and all its resources. This cannot be undone.</p>
      </Modal>
    </div>,
    document.body
  );
}
