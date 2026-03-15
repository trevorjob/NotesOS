'use client';

import { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';
import { TextInputUnderline } from '@/components/ui/TextInputUnderline';
import { DatePickerInput } from '@/components/ui/DatePickerInput';
import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { apiClient } from '@/lib/api';

export default function CreateSemesterPage() {
  const router = useRouter();

  const [name, setName]         = useState('');
  const [startDate, setStart]   = useState('');
  const [endDate, setEnd]       = useState('');
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');
  const [nameError, setNameErr] = useState('');

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setNameErr('');
    setError('');
    if (!name.trim()) { setNameErr('Semester name is required'); return; }

    setLoading(true);
    try {
      const payload: Record<string, string> = { name: name.trim() };
      if (startDate) payload.start_date = startDate;
      if (endDate)   payload.end_date   = endDate;

      const res = await apiClient.post('/api/semesters', payload);
      router.push(`/semesters/${res.data.id}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Failed to create semester.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="px-4 md:px-8 py-6 max-w-lg mx-auto">
      <button
        onClick={() => router.back()}
        className="flex items-center gap-1.5 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors mb-8"
      >
        <Icon name="arrow_back" size="xs" /> Back
      </button>

      <h1 className="font-display font-bold text-2xl text-[var(--text-primary)] mb-1">
        New Semester
      </h1>
      <p className="text-sm text-[var(--text-secondary)] mb-10">
        Group courses together and share with classmates via an invite code.
      </p>

      {error && (
        <div className="mb-6 flex items-start gap-2 px-4 py-3 bg-[var(--error-bg)] rounded-xl">
          <Icon name="error" size="xs" className="text-[var(--color-error)] flex-shrink-0 mt-0.5" />
          <p className="text-sm text-[var(--error-text)]">{error}</p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-7">
        <TextInputUnderline
          label="Semester name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          error={nameError}
          placeholder="e.g. Fall 2026"
          size="lg"
          serif
        />
        <div className="grid grid-cols-2 gap-5">
          <DatePickerInput
            label="Start date (optional)"
            value={startDate}
            onChange={(e) => setStart(e.target.value)}
          />
          <DatePickerInput
            label="End date (optional)"
            value={endDate}
            onChange={(e) => setEnd(e.target.value)}
            min={startDate || undefined}
          />
        </div>

        <div className="flex gap-3 pt-4">
          <Button variant="secondary" size="md" onClick={() => router.back()} disabled={loading} type="button" fullWidth>
            Cancel
          </Button>
          <Button variant="primary" size="md" loading={loading} type="submit" fullWidth>
            Create Semester
          </Button>
        </div>
      </form>
    </div>
  );
}
