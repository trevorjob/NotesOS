'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useCourseStore } from '@/stores/courses';
import { api } from '@/lib/api';
import { Modal } from '@/components/ui/Modal';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';

const EXPANDED_KEY = 'notesos-sidebar-expanded';

function ChevronRight({ className = '' }: { className?: string }) {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" className={className}>
      <path d="M5 3l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function PlusIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M7 2v10M2 7h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

interface NavItemProps { href: string; label: string; icon: React.ReactNode; active: boolean; onClick?: () => void }
function NavItem({ href, label, icon, active, onClick }: NavItemProps) {
  return (
    <Link
      href={href}
      onClick={onClick}
      className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
        active ? 'bg-white/15 text-white font-medium' : 'text-[#9e9a94] hover:text-white hover:bg-white/5'
      }`}
    >
      <span className="shrink-0 opacity-80">{icon}</span>
      {label}
    </Link>
  );
}

interface SidebarProps {
  onClose?: () => void;
}

type JoinTab = 'course' | 'class' | 'search';

export function Sidebar({ onClose }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { courses, fetchCourses, selectCourse, createTopic } = useCourseStore();

  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [loadingTopics, setLoadingTopics] = useState<Record<string, boolean>>({});

  const [showAddCourse, setShowAddCourse] = useState(false);
  const [showJoinCourse, setShowJoinCourse] = useState(false);
  const [showAddTopic, setShowAddTopic] = useState<string | null>(null);
  const [courseForm, setCourseForm] = useState({ code: '', name: '' });
  const [topicForm, setTopicForm] = useState({ title: '' });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');
  const [createdInviteCode, setCreatedInviteCode] = useState<string | null>(null);

  // Join modal state
  const [joinTab, setJoinTab] = useState<JoinTab>('course');
  const [joinCourseCode, setJoinCourseCode] = useState('');
  const [joinClassCode, setJoinClassCode] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [joiningCourse, setJoiningCourse] = useState(false);
  const [joiningClass, setJoiningClass] = useState(false);
  const [searching, setSearching] = useState(false);
  const [joinSuccess, setJoinSuccess] = useState<{ type: 'course' | 'class'; names: string[] } | null>(null);

  useEffect(() => {
    fetchCourses();
    try {
      const saved = localStorage.getItem(EXPANDED_KEY);
      if (saved) setExpanded(JSON.parse(saved));
    } catch { /* ignore */ }
  }, [fetchCourses]);

  async function toggleCourse(courseId: string) {
    const isCurrentlyExpanded = !!expanded[courseId];
    const next = { ...expanded, [courseId]: !isCurrentlyExpanded };
    setExpanded(next);
    localStorage.setItem(EXPANDED_KEY, JSON.stringify(next));

    if (!isCurrentlyExpanded) {
      const course = courses.find((c) => c.id === courseId);
      if (!course?.topics?.length) {
        setLoadingTopics((prev) => ({ ...prev, [courseId]: true }));
        try {
          await selectCourse(courseId);
        } finally {
          setLoadingTopics((prev) => ({ ...prev, [courseId]: false }));
        }
      }
    }
  }

  function navigate(href: string) {
    router.push(href);
    onClose?.();
  }

  async function handleCreateCourse() {
    if (!courseForm.code.trim() || !courseForm.name.trim()) {
      setFormError('Course code and name are required.');
      return;
    }
    setSaving(true);
    setFormError('');
    try {
      const res = await api.courses.create({ code: courseForm.code.trim(), name: courseForm.name.trim() });
      const course = res.data?.course ?? res.data;
      await fetchCourses(true);
      setCourseForm({ code: '', name: '' });
      setShowAddCourse(false);
      if (course?.invite_code) setCreatedInviteCode(course.invite_code);
    } catch (e: any) {
      setFormError(e.response?.data?.detail || e.message || 'Failed to create course.');
    } finally {
      setSaving(false);
    }
  }

  async function handleJoinByCourseCode() {
    if (!joinCourseCode.trim()) { setFormError('Enter an invite code.'); return; }
    setJoiningCourse(true); setFormError('');
    try {
      const res = await api.courses.join({ invite_code: joinCourseCode.trim() });
      const joined = res.data?.course ?? res.data;
      await fetchCourses(true);
      setJoinSuccess({ type: 'course', names: [joined?.name ?? joined?.code ?? 'the course'] });
    } catch (e: any) {
      setFormError(e.response?.data?.detail || 'Invalid invite code.');
    } finally { setJoiningCourse(false); }
  }

  async function handleJoinByClassCode() {
    if (!joinClassCode.trim()) { setFormError('Enter a class code.'); return; }
    setJoiningClass(true); setFormError('');
    try {
      const res = await api.invites.joinClass(joinClassCode.trim());
      const joined: Array<{ name?: string; code?: string }> = res.data?.courses ?? res.data ?? [];
      await fetchCourses(true);
      setJoinSuccess({ type: 'class', names: joined.map((c) => c.name ?? c.code ?? '?') });
    } catch (e: any) {
      setFormError(e.response?.data?.detail || 'Invalid class code.');
    } finally { setJoiningClass(false); }
  }

  function resetJoin() {
    setJoinCourseCode(''); setJoinClassCode(''); setSearchQuery('');
    setFormError(''); setJoinSuccess(null); setJoinTab('course');
  }

  async function handleCreateTopic(courseId: string) {
    if (!topicForm.title.trim()) {
      setFormError('Topic title is required.');
      return;
    }
    setSaving(true);
    setFormError('');
    try {
      const course = courses.find((c) => c.id === courseId);
      const orderIndex = (course?.topics?.length ?? 0) + 1;
      await createTopic(courseId, { title: topicForm.title.trim(), order_index: orderIndex });
      setTopicForm({ title: '' });
      setShowAddTopic(null);
      setExpanded((prev) => {
        const next = { ...prev, [courseId]: true };
        localStorage.setItem(EXPANDED_KEY, JSON.stringify(next));
        return next;
      });
    } catch (e: any) {
      setFormError(e.message || 'Failed to create topic.');
    } finally {
      setSaving(false);
    }
  }

  const globalNavItems = [
    {
      href: '/home',
      label: 'Home',
      icon: (
        <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
          <path d="M2 6.5L7.5 2L13 6.5V13H9.5V9H5.5V13H2V6.5Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/>
        </svg>
      ),
    },
    {
      href: '/progress',
      label: 'Progress',
      icon: (
        <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
          <path d="M2 11L5 7l3 3 3-4 2 2" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      ),
    },
    {
      href: '/generate-test',
      label: 'Generate Test',
      icon: (
        <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
          <path d="M4 4h7M4 7h5M4 10h3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
          <path d="M11 10l1.5 2" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
          <circle cx="10.5" cy="9" r="2" stroke="currentColor" strokeWidth="1.4"/>
        </svg>
      ),
    },
  ];

  return (
    <>
      <nav className="w-60 shrink-0 bg-[#1a1917] text-white flex flex-col h-full overflow-y-auto">
        {/* Mobile close button */}
        {onClose && (
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
            <span className="text-sm font-semibold text-white">Menu</span>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-white/10 text-[#9e9a94] hover:text-white transition-colors"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </button>
          </div>
        )}

        {/* Global nav */}
        <div className="px-3 pt-4 pb-2 space-y-0.5">
          {globalNavItems.map((item) => (
            <NavItem
              key={item.href}
              href={item.href}
              label={item.label}
              icon={item.icon}
              active={pathname === item.href || (item.href !== '/home' && pathname.startsWith(item.href))}
              onClick={onClose}
            />
          ))}
        </div>

        {/* Divider + Courses label */}
        <div className="mx-3 border-t border-white/10 mt-2 pt-3 pb-1">
          <p className="px-1 text-[10px] font-semibold text-[#6b6762] uppercase tracking-widest">Courses</p>
        </div>

        {/* Course list */}
        <div className="flex-1 py-1 space-y-0.5 overflow-y-auto">
          {courses.map((course) => {
            const isExpanded = !!expanded[course.id];
            const isLoadingThisCourse = !!loadingTopics[course.id];

            return (
              <div key={course.id}>
                <button
                  onClick={() => toggleCourse(course.id)}
                  className="w-full flex items-center gap-2 px-4 py-2 text-sm font-medium text-[#c8c4be] hover:text-white hover:bg-white/5 transition-colors text-left"
                >
                  <ChevronRight className={`shrink-0 transition-transform duration-150 ${isExpanded ? 'rotate-90' : ''}`} />
                  <span className="truncate flex-1">{course.code}</span>
                  {isLoadingThisCourse && (
                    <span className="h-3 w-3 rounded-full border border-white/30 border-t-white animate-spin shrink-0" />
                  )}
                </button>

                {isExpanded && (
                  <div className="ml-6 border-l border-white/10 pl-2 pb-1 space-y-0.5">
                    {(course.topics ?? []).length === 0 && !isLoadingThisCourse && (
                      <p className="px-3 py-1.5 text-xs text-[#6b6762] italic">No topics yet</p>
                    )}

                    {(course.topics ?? []).map((topic) => {
                      const href = `/courses/${course.id}/topics/${topic.id}`;
                      const active = pathname === href;
                      return (
                        <button
                          key={topic.id}
                          onClick={() => navigate(href)}
                          className={`w-full text-left px-3 py-1.5 text-sm rounded-md truncate transition-colors ${
                            active
                              ? 'bg-white text-[#1a1917] font-medium'
                              : 'text-[#9e9a94] hover:text-white hover:bg-white/5'
                          }`}
                        >
                          {topic.title}
                        </button>
                      );
                    })}

                    <button
                      onClick={() => { setShowAddTopic(course.id); setFormError(''); setTopicForm({ title: '' }); }}
                      className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-[#6b6762] hover:text-[#9e9a94] transition-colors"
                    >
                      <PlusIcon /> New topic
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Footer */}
        <div className="border-t border-white/10 p-4 space-y-1">
          <button
            onClick={() => { setShowAddCourse(true); setFormError(''); setCourseForm({ code: '', name: '' }); }}
            className="flex items-center gap-2 text-sm text-[#6b6762] hover:text-[#9e9a94] transition-colors w-full"
          >
            <PlusIcon /> Create Course
          </button>
          <button
            onClick={() => { setShowJoinCourse(true); resetJoin(); }}
            className="flex items-center gap-2 text-sm text-[#6b6762] hover:text-[#9e9a94] transition-colors w-full"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M9 1H12a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H9M5 10l4-4-4-4M9 7H1" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Join Course / Class
          </button>
        </div>
      </nav>

      {/* Create Course modal */}
      <Modal isOpen={showAddCourse} onClose={() => setShowAddCourse(false)} title="Create Course">
        <div className="space-y-3">
          <Input label="Course Code" value={courseForm.code} onChange={(e) => setCourseForm((f) => ({ ...f, code: e.target.value }))} placeholder="e.g. CS301" />
          <Input label="Course Name" value={courseForm.name} onChange={(e) => setCourseForm((f) => ({ ...f, name: e.target.value }))} placeholder="e.g. Operating Systems" />
          {formError && <p className="text-sm text-[#dc2626]">{formError}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" size="sm" onClick={() => setShowAddCourse(false)}>Cancel</Button>
            <Button size="sm" loading={saving} onClick={handleCreateCourse}>Create</Button>
          </div>
        </div>
      </Modal>

      {/* New Topic modal */}
      <Modal isOpen={!!showAddTopic} onClose={() => setShowAddTopic(null)} title="New Topic">
        <div className="space-y-3">
          <Input label="Topic Title" value={topicForm.title} onChange={(e) => setTopicForm({ title: e.target.value })} placeholder="e.g. Week 4 — Memory Management" />
          {formError && <p className="text-sm text-[#dc2626]">{formError}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" size="sm" onClick={() => setShowAddTopic(null)}>Cancel</Button>
            <Button size="sm" loading={saving} onClick={() => showAddTopic && handleCreateTopic(showAddTopic)}>Create</Button>
          </div>
        </div>
      </Modal>

      {/* Invite code after creation */}
      {createdInviteCode && (
        <Modal isOpen onClose={() => setCreatedInviteCode(null)} title="Course Created!">
          <div className="space-y-4 text-center">
            <p className="text-xs text-[#6b6762]">Share this code so classmates can join:</p>
            <div className="flex items-center gap-2 bg-[#f0eeea] rounded-xl px-4 py-3">
              <p className="flex-1 font-mono text-base font-semibold text-[#1a1917] tracking-widest">{createdInviteCode}</p>
              <button
                onClick={() => navigator.clipboard.writeText(createdInviteCode)}
                className="text-xs text-[#6b6762] hover:text-[#1a1917] px-2 py-1 rounded-lg hover:bg-white transition-colors"
              >
                Copy
              </button>
            </div>
            <Button size="sm" onClick={() => setCreatedInviteCode(null)}>Done</Button>
          </div>
        </Modal>
      )}

      {/* Join modal */}
      <Modal isOpen={showJoinCourse} onClose={() => { setShowJoinCourse(false); resetJoin(); }} title="Join">
        {joinSuccess ? (
          <div className="text-center space-y-3 py-2">
            <div className="text-3xl">✓</div>
            {joinSuccess.type === 'course' ? (
              <p className="text-sm font-medium text-[#1a1917]">Joined <strong>{joinSuccess.names[0]}</strong>!</p>
            ) : (
              <div>
                <p className="text-sm font-medium text-[#1a1917]">Joined {joinSuccess.names.length} course{joinSuccess.names.length !== 1 ? 's' : ''}!</p>
                <p className="text-xs text-[#6b6762] mt-1">{joinSuccess.names.join(', ')}</p>
              </div>
            )}
            <Button size="sm" onClick={() => { setShowJoinCourse(false); resetJoin(); }}>Done</Button>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Tabs */}
            <div className="flex gap-1 bg-[#f0eeea] rounded-xl p-1">
              {([['course', 'Course code'], ['class', 'Join class'], ['search', 'Search']] as const).map(([t, label]) => (
                <button
                  key={t}
                  onClick={() => { setJoinTab(t); setFormError(''); }}
                  className={`flex-1 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    joinTab === t ? 'bg-white text-[#1a1917] shadow-sm' : 'text-[#6b6762]'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            {joinTab === 'course' && (
              <div className="space-y-3">
                <Input
                  label="Course invite code"
                  value={joinCourseCode}
                  onChange={(e) => setJoinCourseCode(e.target.value)}
                  placeholder="e.g. BIO201-XK92"
                />
                {formError && <p className="text-sm text-[#dc2626]">{formError}</p>}
                <Button loading={joiningCourse} onClick={handleJoinByCourseCode} className="w-full">Join Course</Button>
              </div>
            )}

            {joinTab === 'class' && (
              <div className="space-y-3">
                <p className="text-xs text-[#6b6762]">Joining a class enrolls you in all courses from that classmate at once.</p>
                <Input
                  label="Class invite code"
                  value={joinClassCode}
                  onChange={(e) => setJoinClassCode(e.target.value)}
                  placeholder="e.g. XK92-ABCD"
                />
                {formError && <p className="text-sm text-[#dc2626]">{formError}</p>}
                <Button loading={joiningClass} onClick={handleJoinByClassCode} className="w-full">Join Class</Button>
              </div>
            )}

            {joinTab === 'search' && (
              <div className="space-y-3">
                <Input
                  label="Search by course name"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="e.g. Operating Systems"
                />
                <p className="text-xs text-[#9e9a94]">Search is coming soon. Use a course or class code instead.</p>
              </div>
            )}
          </div>
        )}
      </Modal>
    </>
  );
}
