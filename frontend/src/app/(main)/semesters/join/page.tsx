'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { InviteCodeInput } from '@/components/ui/InviteCodeInput';
import { Button } from '@/components/ui/Button';
import { Icon } from '@/components/ui/Icon';
import { apiClient } from '@/lib/api';

interface SemesterPreview {
  id: string;
  name: string;
  owner_name: string;
  course_count: number;
  member_count: number;
  start_date?: string;
  end_date?: string;
}

export default function JoinSemesterPage() {
  const router = useRouter();
  const [code, setCode]             = useState('');
  const [preview, setPreview]       = useState<SemesterPreview | null>(null);
  const [loading, setLoading]       = useState(false);
  const [joining, setJoining]       = useState(false);
  const [error, setError]           = useState('');
  const [step, setStep]             = useState<'enter' | 'preview'>('enter');

  const handleLookup = async () => {
    setError('');
    setLoading(true);
    try {
      const res = await apiClient.post('/api/semesters/join', { invite_code: code, preview: true });
      setPreview(res.data);
      setStep('preview');
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Invalid invite code.');
    } finally {
      setLoading(false);
    }
  };

  const handleJoin = async () => {
    setError('');
    setJoining(true);
    try {
      const res = await apiClient.post('/api/semesters/join', { invite_code: code });
      router.push(`/semesters/${res.data.semester_id ?? res.data.id}`);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? 'Failed to join semester.');
    } finally {
      setJoining(false);
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
        Join a Semester
      </h1>
      <p className="text-sm text-[var(--text-secondary)] mb-8">
        Enter the invite code shared by your classmate or instructor.
      </p>

      {step === 'enter' && (
        <InviteCodeInput
          value={code}
          onChange={setCode}
          onJoin={handleLookup}
          loading={loading}
          error={error}
          placeholder="e.g. SPRING26"
        />
      )}

      {step === 'preview' && preview && (
        <div className="flex flex-col gap-5">
          <div className="glass-card p-6">
            <p className="text-xs uppercase tracking-widest font-bold text-[var(--text-tertiary)] mb-2">
              Semester Preview
            </p>
            <h2 className="font-display font-semibold text-xl text-[var(--text-primary)] mb-4">
              {preview.name}
            </h2>
            <div className="grid grid-cols-2 gap-4">
              <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
                <Icon name="person" size="xs" /> {preview.owner_name}
              </div>
              <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
                <Icon name="group" size="xs" /> {preview.member_count} members
              </div>
              <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
                <Icon name="school" size="xs" /> {preview.course_count} courses
              </div>
            </div>
          </div>

          {error && (
            <div className="flex items-start gap-2 px-4 py-3 bg-[var(--error-bg)] rounded-xl">
              <Icon name="error" size="xs" className="text-[var(--color-error)] flex-shrink-0 mt-0.5" />
              <p className="text-sm text-[var(--error-text)]">{error}</p>
            </div>
          )}

          <div className="flex gap-3">
            <Button variant="secondary" size="md" onClick={() => { setStep('enter'); setPreview(null); setError(''); }} fullWidth>
              Back
            </Button>
            <Button variant="primary" size="md" onClick={handleJoin} loading={joining} iconLeft="group_add" fullWidth>
              Join Semester
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
