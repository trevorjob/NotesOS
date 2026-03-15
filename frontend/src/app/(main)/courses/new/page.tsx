'use client';

import { FormEvent, useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { TextInputUnderline } from '@/components/ui/TextInputUnderline';
import { Textarea } from '@/components/ui/Textarea';
import { Select } from '@/components/ui/Select';
import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { apiClient } from '@/lib/api';

interface Semester {
  id: string;
  name: string;
}

export default function CreateCoursePage() {
  const router = useRouter();

  const [code, setCode]           = useState('');
  const [name, setName]           = useState('');
  const [description, setDesc]    = useState('');
  const [semesterId, setSemId]    = useState('');
  const [semesters, setSemesters] = useState<Semester[]>([]);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState('');
  const [errors, setErrors]       = useState<Record<string, string>>({});

  useEffect(() => {
    apiClient.get('/api/semesters')
      .then((r) => setSemesters(r.data.semesters ?? []))
      .catch(() => {});
  }, []);

  const validate = (): boolean => {
    const errs: Record<string, string> = {};
    if (!code.trim()) errs.code = 'Course code is required';
    if (!name.trim()) errs.name = 'Course name is required';
    setErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    setLoading(true);
    setError('');
    try {
      const payload: Record<string, string> = {
        code: code.trim().toUpperCase(),
        name: name.trim(),
      };
      if (description.trim()) payload.description = description.trim();
      if (semesterId) payload.semester_id = semesterId;

      const res = await apiClient.post('/api/courses', payload);
      router.push(`/courses/${res.data.id}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Failed to create course.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="px-4 md:px-8 py-6 max-w-lg mx-auto">
      {/* Back */}
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1.5 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors mb-8"
      >
        <Icon name="arrow_back" size="xs" /> Courses
      </button>

      <h1 className="font-display font-bold text-2xl text-[var(--text-primary)] mb-1">
        New Course
      </h1>
      <p className="text-sm text-[var(--text-secondary)] mb-10">
        Create a course to organise your topics and resources.
      </p>

      {error && (
        <div className="mb-6 flex items-start gap-2 px-4 py-3 bg-[var(--error-bg)] rounded-xl">
          <Icon name="error" size="xs" className="text-[var(--color-error)] flex-shrink-0 mt-0.5" />
          <p className="text-sm text-[var(--error-text)]">{error}</p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-7">
        <TextInputUnderline
          label="Course code"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          error={errors.code}
          placeholder="e.g. CS101"
          size="lg"
          serif
        />
        <TextInputUnderline
          label="Course name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          error={errors.name}
          placeholder="e.g. Introduction to Computer Science"
          size="lg"
          serif
        />
        <Textarea
          label="Description (optional)"
          value={description}
          onChange={(e) => setDesc(e.target.value)}
          placeholder="Brief description of this course…"
          rows={3}
        />
        {semesters.length > 0 && (
          <Select
            label="Semester (optional)"
            value={semesterId}
            onChange={(e) => setSemId(e.target.value)}
            options={semesters.map((s) => ({ value: s.id, label: s.name }))}
            placeholder="— No semester —"
          />
        )}

        <div className="flex gap-3 pt-4">
          <Button variant="secondary" size="md" onClick={() => router.back()} disabled={loading} type="button" fullWidth>
            Cancel
          </Button>
          <Button variant="primary" size="md" loading={loading} type="submit" fullWidth>
            Create Course
          </Button>
        </div>
      </form>
    </div>
  );
}
