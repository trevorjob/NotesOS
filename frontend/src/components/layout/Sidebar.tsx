'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useCourseStore } from '@/stores/courses';
import { useSemesterStore } from '@/stores/semesters';
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


export function Sidebar({ onClose }: SidebarProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { courses, fetchCourses, selectCourse, createTopic } = useCourseStore();
  const { semesters, activeSemesterId, fetchSemesters, joinSemester } = useSemesterStore();

  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [loadingTopics, setLoadingTopics] = useState<Record<string, boolean>>({});

  const [showAddCourse, setShowAddCourse] = useState(false);
  const [showJoinCourse, setShowJoinCourse] = useState(false);
  const [showAddTopic, setShowAddTopic] = useState<string | null>(null);
  const [courseForm, setCourseForm] = useState({ code: '', name: '' });
  const [topicForm, setTopicForm] = useState({ title: '' });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState('');

  // Join modal state
  const [joinSemesterCode, setJoinSemesterCode] = useState('');
  const [joiningSemester, setJoiningSemester] = useState(false);
  const [joinSuccess, setJoinSuccess] = useState<string | null>(null);

  useEffect(() => {
    fetchCourses();
    fetchSemesters();
    try {
      const saved = localStorage.getItem(EXPANDED_KEY);
      if (saved) setExpanded(JSON.parse(saved));
    } catch { /* ignore */ }
  }, [fetchCourses, fetchSemesters]);

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
    if (!activeSemesterId) {
      setFormError('No active semester. Go to Settings to create or select one.');
      return;
    }
    setSaving(true);
    setFormError('');
    try {
      const res = await api.courses.create({
        code: courseForm.code.trim(),
        name: courseForm.name.trim(),
        semester_id: activeSemesterId,
      });
      const course = res.data?.course ?? res.data;
      await fetchCourses(true);
      setCourseForm({ code: '', name: '' });
      setShowAddCourse(false);
    } catch (e: any) {
      setFormError(e.response?.data?.detail || e.message || 'Failed to create course.');
    } finally {
      setSaving(false);
    }
  }

  async function handleJoinBySemesterCode() {
    if (!joinSemesterCode.trim()) { setFormError('Enter a semester code.'); return; }
    setJoiningSemester(true); setFormError('');
    try {
      const res = await joinSemester(joinSemesterCode.trim());
      await fetchCourses(true);
      const count = (res?.courses_joined ?? []).length;
      setJoinSuccess(`Joined semester — enrolled in ${count} course${count !== 1 ? 's' : ''}`);
    } catch (e: unknown) {
      setFormError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || 'Invalid semester code.');
    } finally { setJoiningSemester(false); }
  }

  function resetJoin() {
    setJoinSemesterCode('');
    setFormError(''); setJoinSuccess(null);
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
      const newTopic = await createTopic(courseId, { title: topicForm.title.trim(), order_index: orderIndex });
      setTopicForm({ title: '' });
      setShowAddTopic(null);
      setExpanded((prev) => {
        const next = { ...prev, [courseId]: true };
        localStorage.setItem(EXPANDED_KEY, JSON.stringify(next));
        return next;
      });
      const topicId = newTopic?.topic?.id ?? newTopic?.id;
      if (topicId) {
        navigate(`/courses/${courseId}/topics/${topicId}`);
      }
    } catch (e: unknown) {
      setFormError((e as Error).message || 'Failed to create topic.');
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

        {/* Course list — grouped by semester */}
        <div className="flex-1 py-1 overflow-y-auto">
          {(() => {
            // Courses carry semester_id — use that to group
            const ungrouped = courses.filter((c) => !c.semester_id);

            function renderCourse(course: typeof courses[0]) {
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
                              active ? 'bg-white text-[#1a1917] font-medium' : 'text-[#9e9a94] hover:text-white hover:bg-white/5'
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
            }

            return (
              <div className="space-y-0.5">
                {/* Semester groups */}
                {semesters.map((semester) => {
                  const semCourses = courses.filter((c) => c.semester_id === semester.id);
                  if (semCourses.length === 0) return null;
                  const isActive = activeSemesterId === semester.id;
                  return (
                    <div key={semester.id}>
                      <div className="flex items-center gap-1.5 px-4 pt-2 pb-1">
                        <p className={`text-[10px] font-semibold uppercase tracking-widest truncate ${isActive ? 'text-[#1a1917]' : 'text-[#4a4744]'}`}>
                          {semester.name}
                        </p>
                        {isActive && (
                          <span className="text-[9px] bg-[#1a1917] text-white px-1.5 py-0.5 rounded-full shrink-0">current</span>
                        )}
                      </div>
                      {semCourses.map(renderCourse)}
                    </div>
                  );
                })}

                {/* Ungrouped courses */}
                {ungrouped.length > 0 && semesters.length > 0 && (
                  <p className="px-4 pt-2 pb-1 text-[10px] font-semibold text-[#4a4744] uppercase tracking-widest">Other</p>
                )}
                {ungrouped.map(renderCourse)}
              </div>
            );
          })()}
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
            Join Semester
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

      {/* Join Semester modal */}
      <Modal isOpen={showJoinCourse} onClose={() => { setShowJoinCourse(false); resetJoin(); }} title="Join Semester">
        {joinSuccess ? (
          <div className="text-center space-y-3 py-2">
            <div className="text-3xl">✓</div>
            <p className="text-sm font-medium text-[#1a1917]">{joinSuccess}</p>
            <Button size="sm" onClick={() => { setShowJoinCourse(false); resetJoin(); }}>Done</Button>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-xs text-[#6b6762]">Enter a semester invite code to join all courses within that semester.</p>
            <Input
              label="Semester invite code"
              value={joinSemesterCode}
              onChange={(e) => setJoinSemesterCode(e.target.value)}
              placeholder="e.g. AB3C4D5E"
              onKeyDown={(e) => e.key === 'Enter' && handleJoinBySemesterCode()}
            />
            {formError && <p className="text-sm text-[#dc2626]">{formError}</p>}
            <Button loading={joiningSemester} onClick={handleJoinBySemesterCode} className="w-full">Join Semester</Button>
          </div>
        )}
      </Modal>
    </>
  );
}
