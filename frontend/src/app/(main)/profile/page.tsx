'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import { Avatar } from '@/components/data-display/Avatar';
import { ToggleSwitch } from '@/components/ui/ToggleSwitch';
import { PillTag } from '@/components/ui/PillTag';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/feedback/Modal';
import { Icon } from '@/components/ui/Icon';
import { apiClient } from '@/lib/api';
import { useToast } from '@/components/feedback/ToastProvider';

const PERSONALITY_TAGS = [
  'Visual Learner', 'Deep Diver', 'Quick Recap', 'Detail-Oriented',
  'Big Picture', 'Practice-Focused', 'Conceptual', 'Exam-Ready',
];

const TONE_OPTIONS = [
  { id: 'encouraging', label: 'Encouraging' },
  { id: 'direct',      label: 'Direct' },
  { id: 'humorous',    label: 'Humorous' },
];

const STYLE_OPTIONS = [
  { id: 'detailed', label: 'Detailed' },
  { id: 'concise',  label: 'Concise' },
  { id: 'visual',   label: 'Visual' },
];

export default function ProfilePage() {
  const router = useRouter();
  const toast = useToast();
  const { user, logout, updatePersonality } = useAuthStore();

  const [tone, setTone]     = useState<'encouraging' | 'direct' | 'humorous'>(user?.study_personality?.tone ?? 'encouraging');
  const [style, setStyle]   = useState<'detailed' | 'concise' | 'visual'>(user?.study_personality?.explanation_style ?? 'detailed');
  const [tags, setTags]     = useState<string[]>((user as any)?.personality_tags ?? []);
  const [darkMode, setDark] = useState(false);
  const [notifications, setNotif] = useState(true);
  const [logoutModal, setLogoutModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);

  const toggleTag = (t: string) =>
    setTags((prev) => prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t]);

  const handleSavePersonality = async () => {
    setSaving(true);
    try {
      await updatePersonality({ tone: tone as any, explanation_style: style as any });
      await apiClient.patch('/api/auth/me/preferences', { personality_tags: tags });
      toast.success('Preferences saved!');
    } catch {
      toast.error('Failed to save preferences.');
    } finally {
      setSaving(false);
    }
  };

  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      await logout();
      router.push('/login');
    } finally {
      setLoggingOut(false);
    }
  };

  return (
    <div className="px-4 md:px-8 py-6 max-w-lg mx-auto">
      <h1 className="font-display font-bold text-xl text-[var(--text-primary)] mb-8">Profile</h1>

      {/* User info */}
      <section className="glass-card p-6 mb-5">
        <div className="flex items-center gap-4">
          <Avatar name={user?.full_name ?? 'User'} size="lg" />
          <div>
            <p className="font-semibold text-[var(--text-primary)] text-lg">{user?.full_name}</p>
            <p className="text-sm text-[var(--text-secondary)]">{user?.email}</p>
          </div>
        </div>
      </section>

      {/* App preferences */}
      <section className="glass-card p-6 mb-5">
        <h2 className="text-xs uppercase tracking-widest font-bold text-[var(--text-tertiary)] mb-4">
          App Settings
        </h2>
        <div className="flex flex-col gap-4">
          <ToggleSwitch
            checked={darkMode}
            onChange={(v) => {
              setDark(v);
              document.documentElement.classList.toggle('dark', v);
            }}
            label="Dark mode"
            description="Switch to a dark theme"
          />
          <ToggleSwitch
            checked={notifications}
            onChange={setNotif}
            label="Push notifications"
            description="Get notified when tests are graded"
          />
        </div>
      </section>

      {/* AI personality */}
      <section className="glass-card p-6 mb-5">
        <h2 className="text-xs uppercase tracking-widest font-bold text-[var(--text-tertiary)] mb-4">
          AI Personality
        </h2>

        {/* Tone */}
        <div className="mb-5">
          <p className="text-sm font-medium text-[var(--text-primary)] mb-2">Response Tone</p>
          <div className="flex flex-wrap gap-2">
            {TONE_OPTIONS.map((opt) => (
              <PillTag key={opt.id} label={opt.label} selected={tone === opt.id} onClick={() => setTone(opt.id as typeof tone)} />
            ))}
          </div>
        </div>

        {/* Style */}
        <div className="mb-5">
          <p className="text-sm font-medium text-[var(--text-primary)] mb-2">Explanation Style</p>
          <div className="flex flex-wrap gap-2">
            {STYLE_OPTIONS.map((opt) => (
              <PillTag key={opt.id} label={opt.label} selected={style === opt.id} onClick={() => setStyle(opt.id as typeof style)} />
            ))}
          </div>
        </div>

        {/* Tags */}
        <div className="mb-6">
          <p className="text-sm font-medium text-[var(--text-primary)] mb-2">Learning Tags</p>
          <div className="flex flex-wrap gap-2">
            {PERSONALITY_TAGS.map((t) => (
              <PillTag key={t} label={t} selected={tags.includes(t)} onClick={() => toggleTag(t)} />
            ))}
          </div>
        </div>

        <Button variant="primary" size="md" loading={saving} onClick={handleSavePersonality}>
          Save Preferences
        </Button>
      </section>

      {/* Sign out */}
      <section className="glass-card p-6">
        <Button
          variant="ghost"
          size="md"
          onClick={() => setLogoutModal(true)}
          iconLeft="logout"
          className="text-[var(--color-error)] hover:bg-[var(--error-bg)]"
        >
          Sign out
        </Button>
      </section>

      <Modal
        open={logoutModal}
        onClose={() => setLogoutModal(false)}
        title="Sign out?"
        variant="destructive"
        confirmLabel="Sign out"
        onConfirm={handleLogout}
        loading={loggingOut}
      >
        You'll need to sign in again to access your courses.
      </Modal>
    </div>
  );
}
