'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import { useCourseStore } from '@/stores/courses';
import { useSemesterStore } from '@/stores/semesters';
import { api } from '@/lib/api';
import { ContinueStudyingCard } from '@/components/home/ContinueStudyingCard';
import { RecentTopics } from '@/components/home/RecentTopics';
import { Modal } from '@/components/ui/Modal';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  return 'Good evening';
}

// ── Create Course Modal ──────────────────────────────────────────────────────

interface CreatedCourse {
  id: string;
  code: string;
  name: string;
  invite_code?: string;
}

function CreateCourseModal({ isOpen, onClose, onCreated }: {
  isOpen: boolean;
  onClose: () => void;
  onCreated: (course: CreatedCourse) => void;
}) {
  const { semesters: storeSemesters, activeSemesterId } = useSemesterStore();
  const [semesters, setSemesters] = useState<Array<{ id: string; name: string }>>([]);

  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [semesterId, setSemesterId] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!isOpen) return;
    // Use store semesters if already loaded, otherwise fetch
    if (storeSemesters.length > 0) {
      setSemesters(storeSemesters);
    } else {
      api.semesters.getAll().then((r) => setSemesters(r.data?.semesters ?? r.data ?? [])).catch(() => {});
    }
    // Auto-select active semester
    setSemesterId(activeSemesterId ?? '');
  }, [isOpen, storeSemesters, activeSemesterId]);

  function reset() { setCode(''); setName(''); setDescription(''); setSemesterId(''); setError(''); }

  async function handleCreate() {
    if (!code.trim() || !name.trim()) { setError('Course code and name are required.'); return; }
    if (!semesterId) { setError('Select a semester. Create one in Settings first if needed.'); return; }
    setSaving(true); setError('');
    try {
      const res = await api.courses.create({
        code: code.trim(),
        name: name.trim(),
        description: description.trim() || undefined,
        semester_id: semesterId,
      });
      const course = res.data?.course ?? res.data;
      // Also enroll creator — handled server-side
      await useCourseStore.getState().fetchCourses(true);
      reset();
      onCreated(course);
    } catch (e: unknown) {
      setError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Failed to create course.');
    } finally { setSaving(false); }
  }

  return (
    <Modal isOpen={isOpen} onClose={() => { reset(); onClose(); }} title="Create Course">
      <div className="space-y-3">
        <Input label="Course Code *" value={code} onChange={(e) => setCode(e.target.value)} placeholder="e.g. CS301" />
        <Input label="Course Name *" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Operating Systems" />
        <div>
          <label className="mb-1 block text-xs font-medium text-[#6b6762]">Description (optional)</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What is this course about?"
            rows={2}
            className="w-full resize-none rounded-lg border border-[#dedad4] bg-[#f0eeea] px-3 py-2 text-sm text-[#1a1917] placeholder-[#9e9a94] focus:border-[#1a1917] focus:outline-none"
          />
        </div>
        {semesters.length === 0 ? (
          <p className="text-sm text-[#dc2626]">No semesters yet. <a href="/settings#semesters" className="underline">Create one in Settings</a> first.</p>
        ) : semesterId ? (
          <p className="text-xs text-[#6b6762]">Will be added to <strong>{semesters.find((s) => s.id === semesterId)?.name}</strong></p>
        ) : (
          <div>
            <label className="mb-1 block text-xs font-medium text-[#6b6762]">Semester *</label>
            <select
              value={semesterId}
              onChange={(e) => setSemesterId(e.target.value)}
              className="w-full rounded-lg border border-[#dedad4] bg-[#f0eeea] px-3 py-2 text-sm text-[#1a1917] focus:border-[#1a1917] focus:outline-none"
            >
              <option value="">Select a semester</option>
              {semesters.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
        )}
        {error && <p className="text-sm text-[#dc2626]">{error}</p>}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="ghost" size="sm" onClick={() => { reset(); onClose(); }}>Cancel</Button>
          <Button size="sm" loading={saving} onClick={handleCreate}>Create</Button>
        </div>
      </div>
    </Modal>
  );
}

// ── Course Created Screen (redirects to course) ──────────────────────────────

function CourseCreatedScreen({ course, onDone }: { course: CreatedCourse; onDone: () => void }) {
  const router = useRouter();
  return (
    <Modal isOpen onClose={onDone} title="Course Created!">
      <div className="space-y-4 text-center">
        <div className="text-4xl">🎉</div>
        <p className="text-sm font-semibold text-[#1a1917]">{course.code} — {course.name}</p>
        <p className="text-xs text-[#6b6762]">
          To share this course, share your semester invite code from Settings.
        </p>
        <div className="flex justify-center gap-2">
          <Button variant="ghost" size="sm" onClick={onDone}>Done</Button>
          {/* <Button size="sm" onClick={() => { onDone(); router.push(`/courses/${course.id}/topics`); }}>
            Go to course →
          </Button> */}
        </div>
      </div>
    </Modal>
  );
}

// ── Join Semester Modal ──────────────────────────────────────────────────────

function JoinSemesterModal({ isOpen, onClose, onJoined }: {
  isOpen: boolean;
  onClose: () => void;
  onJoined: () => void;
}) {
  const { joinSemester } = useSemesterStore();
  const [code, setCode] = useState('');
  const [joining, setJoining] = useState(false);
  const [result, setResult] = useState<{ semesterName: string; courses: Array<{ name: string }> } | null>(null);
  const [error, setError] = useState('');

  function reset() { setCode(''); setError(''); setResult(null); }

  async function handleJoin() {
    if (!code.trim()) { setError('Enter a semester invite code.'); return; }
    setJoining(true); setError('');
    try {
      const data = await joinSemester(code.trim().toUpperCase());
      const semName = (data as { semester?: { name?: string } })?.semester?.name ?? 'the semester';
      const courses = (data as { courses_joined?: Array<{ name: string }> })?.courses_joined ?? [];
      await useCourseStore.getState().fetchCourses(true);
      setResult({ semesterName: semName, courses });
    } catch (e: unknown) {
      setError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Invalid invite code.');
    } finally { setJoining(false); }
  }

  if (result) {
    return (
      <Modal isOpen={isOpen} onClose={() => { reset(); onClose(); onJoined(); }} title="Joined!">
        <div className="text-center space-y-4 py-2">
          <div className="text-4xl">✓</div>
          <div>
            <p className="text-sm font-medium text-[#1a1917]">You joined <strong>{result.semesterName}</strong></p>
            {result.courses.length > 0 && (
              <p className="text-xs text-[#6b6762] mt-1">
                Enrolled in {result.courses.length} course{result.courses.length !== 1 ? 's' : ''}: {result.courses.map((c) => c.name).join(', ')}
              </p>
            )}
          </div>
          <Button onClick={() => { reset(); onClose(); onJoined(); }}>Go explore →</Button>
        </div>
      </Modal>
    );
  }

  return (
    <Modal isOpen={isOpen} onClose={() => { reset(); onClose(); }} title="Join Semester">
      <div className="space-y-4">
        <p className="text-xs text-[#6b6762]">
          Enter a semester invite code to join all courses within that semester.
        </p>
        <Input
          label="Semester invite code"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="e.g. AB3C4D5E"
          onKeyDown={(e) => e.key === 'Enter' && handleJoin()}
        />
        {error && <p className="text-sm text-[#dc2626]">{error}</p>}
        <Button loading={joining} onClick={handleJoin} className="w-full">
          Join Semester
        </Button>
      </div>
    </Modal>
  );
}

// ── Home Page ────────────────────────────────────────────────────────────────

export default function HomePage() {
  const user = useAuthStore((s) => s.user);
  const { courses, isLoading, fetchCourses } = useCourseStore();
  const { semesters } = useSemesterStore();

  const [showCreate, setShowCreate] = useState(false);
  const [showJoin, setShowJoin] = useState(false);
  const [createdCourse, setCreatedCourse] = useState<CreatedCourse | null>(null);

  useEffect(() => { fetchCourses(); }, [fetchCourses]);

  const firstName = user?.full_name?.split(' ')[0] ?? 'there';
  const hasCourses = courses.length > 0;
  const hasTopics = courses.some((c) => (c.topics?.length ?? 0) > 0);
  const hasSemesters = semesters.length > 0;

  return (
    <div className="mx-auto max-w-3xl space-y-8 px-6 py-8">
      {/* Greeting */}
      <div>
        <h1 className="text-2xl font-semibold text-[#1a1917]">{greeting()}, {firstName}</h1>
        <p className="mt-1 text-sm text-[#6b6762]">What are we studying today?</p>
      </div>

      {/* Semester setup hint — shown to new users with no semesters */}
      {!isLoading && !hasSemesters && (
        <div className="flex items-start gap-3 rounded-xl border border-[#fde047] bg-[#fefce8] px-4 py-3">
          <span className="mt-0.5 shrink-0 text-base">💡</span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-[#713f12]">Set up a semester first</p>
            <p className="mt-0.5 text-xs text-[#854d0e]">
              Semesters keep your courses organised. Create one in Settings before adding courses.
            </p>
          </div>
          <a href="/settings#semesters" className="mt-0.5 shrink-0 text-xs font-medium text-[#713f12] underline underline-offset-2">
            Go to Settings
          </a>
        </div>
      )}

      {/* Empty state — no courses */}
      {!isLoading && !hasCourses && (
        <div className="flex flex-col items-center rounded-2xl border border-[#dedad4] bg-white px-8 py-12 text-center">
          <div className="mb-4 text-4xl">📚</div>
          <h2 className="mb-1 text-lg font-semibold text-[#1a1917]">Add your first course</h2>
          <p className="mb-6 max-w-xs text-sm text-[#6b6762]">
            Create a course or join a classmate&apos;s semester with their invite code.
          </p>
          <div className="flex gap-3">
            <Button onClick={() => setShowCreate(true)}>+ Create Course</Button>
            <Button variant="ghost" onClick={() => setShowJoin(true)}>Join Semester</Button>
          </div>
        </div>
      )}

      {/* Empty state — has courses but no topics */}
      {!isLoading && hasCourses && !hasTopics && (
        <div className="flex flex-col items-center rounded-2xl border border-[#dedad4] bg-white px-8 py-10 text-center">
          <div className="mb-3 text-3xl">📂</div>
          <h2 className="mb-1 text-base font-semibold text-[#1a1917]">No topics yet</h2>
          <p className="text-sm text-[#6b6762]">
            Open a course in the sidebar and add a topic to start uploading materials.
          </p>
        </div>
      )}

      {/* Normal state */}
      {hasTopics && (
        <>
          <ContinueStudyingCard />
          <RecentTopics />
        </>
      )}

      {isLoading && (
        <div className="flex justify-center py-12"><Spinner size="lg" /></div>
      )}

      {/* Modals */}
      <CreateCourseModal
        isOpen={showCreate}
        onClose={() => setShowCreate(false)}
        onCreated={(course) => { setShowCreate(false); setCreatedCourse(course); }}
      />

      {createdCourse && (
        <CourseCreatedScreen course={createdCourse} onDone={() => setCreatedCourse(null)} />
      )}

      <JoinSemesterModal
        isOpen={showJoin}
        onClose={() => setShowJoin(false)}
        onJoined={() => setShowJoin(false)}
      />
    </div>
  );
}
