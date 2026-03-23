'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import { useCourseStore } from '@/stores/courses';
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
  const { createCourse } = useCourseStore();
  const [semesters, setSemesters] = useState<Array<{ id: string; name: string }>>([]);

  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [semesterId, setSemesterId] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!isOpen) return;
    api.semesters.getAll().then((r) => setSemesters(r.data?.semesters ?? r.data ?? [])).catch(() => {});
  }, [isOpen]);

  function reset() { setCode(''); setName(''); setDescription(''); setSemesterId(''); setError(''); }

  async function handleCreate() {
    if (!code.trim() || !name.trim()) { setError('Course code and name are required.'); return; }
    setSaving(true); setError('');
    try {
      const res = await api.courses.create({
        code: code.trim(),
        name: name.trim(),
        description: description.trim() || undefined,
        semester: semesterId || undefined,
      });
      const course = res.data?.course ?? res.data;
      // Also enroll creator — handled server-side
      await useCourseStore.getState().fetchCourses(true);
      reset();
      onCreated(course);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to create course.');
    } finally { setSaving(false); }
  }

  return (
    <Modal isOpen={isOpen} onClose={() => { reset(); onClose(); }} title="Create Course">
      <div className="space-y-3">
        <Input label="Course Code *" value={code} onChange={(e) => setCode(e.target.value)} placeholder="e.g. CS301" />
        <Input label="Course Name *" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Operating Systems" />
        <div>
          <label className="block text-xs font-medium text-[#6b6762] mb-1">Description (optional)</label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What is this course about?"
            rows={2}
            className="w-full resize-none bg-[#f0eeea] border border-[#dedad4] rounded-lg px-3 py-2 text-sm text-[#1a1917] placeholder-[#9e9a94] focus:outline-none focus:border-[#1a1917]"
          />
        </div>
        {semesters.length > 0 && (
          <div>
            <label className="block text-xs font-medium text-[#6b6762] mb-1">Semester (optional)</label>
            <select
              value={semesterId}
              onChange={(e) => setSemesterId(e.target.value)}
              className="w-full bg-[#f0eeea] border border-[#dedad4] rounded-lg px-3 py-2 text-sm text-[#1a1917] focus:outline-none focus:border-[#1a1917]"
            >
              <option value="">No semester</option>
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

// ── Invite Link Screen (shown after creation) ────────────────────────────────

function InviteScreen({ course, onDone }: { course: CreatedCourse; onDone: () => void }) {
  const router = useRouter();
  const [copied, setCopied] = useState(false);
  const code = course.invite_code ?? course.code;

  function copyCode() {
    navigator.clipboard.writeText(code).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000); });
  }

  return (
    <Modal isOpen onClose={onDone} title="Course Created!">
      <div className="space-y-4 text-center">
        <div className="text-4xl">🎉</div>
        <div>
          <p className="text-sm font-semibold text-[#1a1917]">{course.code} — {course.name}</p>
          <p className="text-xs text-[#6b6762] mt-1">Share this code so classmates can join:</p>
        </div>
        <div className="flex items-center gap-2 bg-[#f0eeea] rounded-xl px-4 py-3">
          <p className="flex-1 font-mono text-base font-semibold text-[#1a1917] tracking-widest">{code}</p>
          <button
            onClick={copyCode}
            className="text-xs text-[#6b6762] hover:text-[#1a1917] px-2 py-1 rounded-lg hover:bg-white transition-colors"
          >
            {copied ? '✓ Copied' : 'Copy'}
          </button>
        </div>
        <div className="flex gap-2 justify-center">
          <Button variant="ghost" size="sm" onClick={onDone}>Done</Button>
          <Button size="sm" onClick={() => { onDone(); router.push(`/courses/${course.id}/topics`); }}>
            Go to course →
          </Button>
        </div>
      </div>
    </Modal>
  );
}

// ── Join Course Modal ────────────────────────────────────────────────────────

interface SearchResult {
  id: string;
  code: string;
  name: string;
  member_count?: number;
  semester?: string;
}

function JoinCourseModal({ isOpen, onClose, onJoined }: {
  isOpen: boolean;
  onClose: () => void;
  onJoined: () => void;
}) {
  const [tab, setTab] = useState<'code' | 'class' | 'search'>('code');
  const [inviteCode, setInviteCode] = useState('');
  const [classCode, setClassCode] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [joining, setJoining] = useState<string | null>(null);
  const [success, setSuccess] = useState<{ names: string[]; type: 'course' | 'class' } | null>(null);
  const [error, setError] = useState('');

  function reset() { setInviteCode(''); setClassCode(''); setSearchQuery(''); setSearchResults([]); setError(''); setSuccess(null); }

  async function handleJoinByCode() {
    if (!inviteCode.trim()) { setError('Enter an invite code.'); return; }
    setJoining('code'); setError('');
    try {
      const res = await api.courses.join({ invite_code: inviteCode.trim() });
      const joined = res.data?.course ?? res.data;
      await useCourseStore.getState().fetchCourses(true);
      setSuccess({ names: [joined?.name ?? joined?.code ?? 'the course'], type: 'course' });
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Invalid invite code.');
    } finally { setJoining(null); }
  }

  async function handleJoinByClass() {
    if (!classCode.trim()) { setError('Enter a class code.'); return; }
    setJoining('class'); setError('');
    try {
      const res = await api.invites.joinClass(classCode.trim());
      const joined: Array<{ name?: string; code?: string }> = res.data?.courses ?? res.data ?? [];
      await useCourseStore.getState().fetchCourses(true);
      setSuccess({ names: joined.map((c) => c.name ?? c.code ?? '?'), type: 'class' });
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Invalid class code.');
    } finally { setJoining(null); }
  }

  async function handleSearch() {
    if (!searchQuery.trim()) return;
    setSearching(true); setError('');
    try {
      const res = await api.courses.join({ search: searchQuery.trim() });
      setSearchResults(res.data?.results ?? []);
    } catch {
      setSearchResults([]);
      setError('No courses found. Try a different search term.');
    } finally { setSearching(false); }
  }

  async function handleJoinResult(courseId: string, courseName: string) {
    setJoining(courseId); setError('');
    try {
      await api.courses.join({ invite_code: courseId });
      await useCourseStore.getState().fetchCourses(true);
      setSuccess({ names: [courseName], type: 'course' });
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Could not join course.');
    } finally { setJoining(null); }
  }

  if (success) {
    return (
      <Modal isOpen={isOpen} onClose={() => { reset(); onClose(); onJoined(); }} title="Joined!">
        <div className="text-center space-y-4 py-2">
          <div className="text-4xl">✓</div>
          {success.type === 'class' ? (
            <div>
              <p className="text-sm font-medium text-[#1a1917]">Joined {success.names.length} course{success.names.length !== 1 ? 's' : ''}!</p>
              <p className="text-xs text-[#6b6762] mt-1">{success.names.join(', ')}</p>
            </div>
          ) : (
            <p className="text-sm font-medium text-[#1a1917]">You joined <strong>{success.names[0]}</strong></p>
          )}
          <Button onClick={() => { reset(); onClose(); onJoined(); }}>Go explore →</Button>
        </div>
      </Modal>
    );
  }

  return (
    <Modal isOpen={isOpen} onClose={() => { reset(); onClose(); }} title="Join">
      <div className="space-y-4">
        {/* Tabs */}
        <div className="flex gap-1 bg-[#f0eeea] rounded-xl p-1">
          {([['code', 'Course code'], ['class', 'Join class'], ['search', 'Search']] as const).map(([t, l]) => (
            <button
              key={t}
              onClick={() => { setTab(t); setError(''); }}
              className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                tab === t ? 'bg-white text-[#1a1917] shadow-sm' : 'text-[#6b6762]'
              }`}
            >
              {l}
            </button>
          ))}
        </div>

        {tab === 'code' && (
          <div className="space-y-3">
            <Input
              label="Course invite code"
              value={inviteCode}
              onChange={(e) => setInviteCode(e.target.value)}
              placeholder="e.g. BIO201-XK92"
              onKeyDown={(e) => e.key === 'Enter' && handleJoinByCode()}
            />
            {error && <p className="text-sm text-[#dc2626]">{error}</p>}
            <Button loading={joining === 'code'} onClick={handleJoinByCode} className="w-full">
              Join Course
            </Button>
          </div>
        )}

        {tab === 'class' && (
          <div className="space-y-3">
            <p className="text-xs text-[#6b6762]">Joining a class enrolls you in all courses from that classmate at once.</p>
            <Input
              label="Class invite code"
              value={classCode}
              onChange={(e) => setClassCode(e.target.value)}
              placeholder="e.g. XK92-ABCD"
              onKeyDown={(e) => e.key === 'Enter' && handleJoinByClass()}
            />
            {error && <p className="text-sm text-[#dc2626]">{error}</p>}
            <Button loading={joining === 'class'} onClick={handleJoinByClass} className="w-full">
              Join Class
            </Button>
          </div>
        )}

        {tab === 'search' && (
          <div className="space-y-3">
            <div className="flex gap-2">
              <Input
                placeholder="Search by course name…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                className="flex-1"
              />
              <Button size="sm" loading={searching} onClick={handleSearch}>Search</Button>
            </div>
            {error && <p className="text-sm text-[#dc2626]">{error}</p>}
            {searchResults.length > 0 && (
              <div className="space-y-2">
                {searchResults.map((r) => (
                  <div key={r.id} className="flex items-center gap-3 bg-[#f0eeea] rounded-xl px-4 py-3">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-[#1a1917]">{r.code} · {r.name}</p>
                      <p className="text-xs text-[#9e9a94]">
                        {r.member_count != null ? `${r.member_count} members` : ''}
                        {r.semester ? ` · ${r.semester}` : ''}
                      </p>
                    </div>
                    <Button
                      size="sm"
                      loading={joining === r.id}
                      onClick={() => handleJoinResult(r.id, r.name)}
                    >
                      Join
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
}

// ── Home Page ────────────────────────────────────────────────────────────────

export default function HomePage() {
  const user = useAuthStore((s) => s.user);
  const { courses, isLoading, fetchCourses } = useCourseStore();

  const [showCreate, setShowCreate] = useState(false);
  const [showJoin, setShowJoin] = useState(false);
  const [createdCourse, setCreatedCourse] = useState<CreatedCourse | null>(null);

  useEffect(() => { fetchCourses(); }, [fetchCourses]);

  const firstName = user?.full_name?.split(' ')[0] ?? 'there';
  const hasCourses = courses.length > 0;
  const hasTopics = courses.some((c) => (c.topics?.length ?? 0) > 0);

  return (
    <div className="max-w-3xl mx-auto px-6 py-8 space-y-8">
      {/* Greeting */}
      <div>
        <h1 className="text-2xl font-semibold text-[#1a1917]">{greeting()}, {firstName}</h1>
        <p className="text-sm text-[#6b6762] mt-1">What are we studying today?</p>
      </div>

      {/* Empty state — no courses */}
      {!isLoading && !hasCourses && (
        <div className="bg-white rounded-2xl border border-[#dedad4] px-8 py-12 flex flex-col items-center text-center">
          <div className="text-4xl mb-4">📚</div>
          <h2 className="text-lg font-semibold text-[#1a1917] mb-1">Add your first course</h2>
          <p className="text-sm text-[#6b6762] mb-6 max-w-xs">
            Create a course or join a classmate's with their invite code.
          </p>
          <div className="flex gap-3">
            <Button onClick={() => setShowCreate(true)}>+ Create Course</Button>
            <Button variant="ghost" onClick={() => setShowJoin(true)}>Join Course</Button>
          </div>
        </div>
      )}

      {/* Empty state — has courses but no topics */}
      {!isLoading && hasCourses && !hasTopics && (
        <div className="bg-white rounded-2xl border border-[#dedad4] px-8 py-10 flex flex-col items-center text-center">
          <div className="text-3xl mb-3">📂</div>
          <h2 className="text-base font-semibold text-[#1a1917] mb-1">No topics yet</h2>
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
        <InviteScreen course={createdCourse} onDone={() => setCreatedCourse(null)} />
      )}

      <JoinCourseModal
        isOpen={showJoin}
        onClose={() => setShowJoin(false)}
        onJoined={() => setShowJoin(false)}
      />
    </div>
  );
}
