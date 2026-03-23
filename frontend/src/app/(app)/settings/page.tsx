'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import { api } from '@/lib/api';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Spinner } from '@/components/ui/Spinner';

// ── Types ────────────────────────────────────────────────────────────────────

type Tone = 'encouraging' | 'direct' | 'humorous';
type EmojiUsage = 'none' | 'moderate' | 'heavy';
type ExplanationStyle = 'concise' | 'detailed' | 'visual';

interface Semester { id: string; name: string; is_active: boolean; course_count?: number }
interface ClassInvite { id: string; invite_code: string; name?: string; is_active: boolean }
interface Notification { id: string; title: string; body: string; is_read: boolean; created_at: string }

const NAV = [
  { id: 'profile', label: 'Profile' },
  { id: 'ai-personality', label: 'AI Personality' },
  { id: 'semesters', label: 'Semesters' },
  { id: 'notifications', label: 'Notifications' },
  { id: 'account', label: 'Account' },
];

// ── Sub-components ───────────────────────────────────────────────────────────

function Section({ id, title, subtitle, children }: { id: string; title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <section id={id} className="bg-white rounded-2xl border border-[#dedad4] p-6 space-y-5 scroll-mt-8">
      <div>
        <h2 className="text-base font-semibold text-[#1a1917]">{title}</h2>
        {subtitle && <p className="text-xs text-[#6b6762] mt-0.5">{subtitle}</p>}
      </div>
      {children}
    </section>
  );
}

function OptionCard<T extends string>({ value, label, desc, selected, onClick }: { value: T; label: string; desc: string; selected: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`text-left px-4 py-3 rounded-xl border text-sm transition-colors ${
        selected ? 'border-[#1a1917] bg-[#1a1917] text-white' : 'border-[#dedad4] text-[#1a1917] hover:border-[#9e9a94] bg-white'
      }`}
    >
      <p className="font-medium">{label}</p>
      <p className={`text-xs mt-0.5 ${selected ? 'text-white/70' : 'text-[#9e9a94]'}`}>{desc}</p>
    </button>
  );
}

// ── Main page ────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const { user, setUser, updatePersonality, logout } = useAuthStore();
  const router = useRouter();

  // Profile
  const [fullName, setFullName] = useState(user?.full_name ?? '');
  const [savingName, setSavingName] = useState(false);
  const [nameMsg, setNameMsg] = useState('');
  const [currentPw, setCurrentPw] = useState('');
  const [newPw, setNewPw] = useState('');
  const [confirmPw, setConfirmPw] = useState('');
  const [savingPw, setSavingPw] = useState(false);
  const [pwMsg, setPwMsg] = useState('');
  const [pwError, setPwError] = useState('');

  // AI Personality
  const p = user?.study_personality;
  const [tone, setTone] = useState<Tone>((p?.tone as Tone) ?? 'encouraging');
  const [emoji, setEmoji] = useState<EmojiUsage>((p?.emoji_usage as EmojiUsage) ?? 'moderate');
  const [style, setStyle] = useState<ExplanationStyle>((p?.explanation_style as ExplanationStyle) ?? 'detailed');
  const [savingPersonality, setSavingPersonality] = useState(false);
  const [personalitySaved, setPersonalitySaved] = useState(false);

  // Semesters
  const [semesters, setSemesters] = useState<Semester[]>([]);
  const [loadingSemesters, setLoadingSemesters] = useState(true);
  const [showNewSemester, setShowNewSemester] = useState(false);
  const [newSemesterName, setNewSemesterName] = useState('');
  const [creatingSemester, setCreatingSemester] = useState(false);
  const [semesterError, setSemesterError] = useState('');
  const [editingSemesterId, setEditingSemesterId] = useState<string | null>(null);
  const [editSemesterName, setEditSemesterName] = useState('');

  // Class invite
  const [classInvite, setClassInvite] = useState<ClassInvite | null>(null);
  const [loadingInvite, setLoadingInvite] = useState(true);
  const [creatingInvite, setCreatingInvite] = useState(false);
  const [copiedInvite, setCopiedInvite] = useState(false);

  // Sidebar filter
  const SIDEBAR_FILTER_KEY = 'notesos-sidebar-filter';
  const [sidebarFilter, setSidebarFilter] = useState<'current' | 'all'>('all');
  useEffect(() => {
    setSidebarFilter((localStorage.getItem(SIDEBAR_FILTER_KEY) as 'current' | 'all') ?? 'all');
  }, []);

  // Notifications
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loadingNotifs, setLoadingNotifs] = useState(true);
  const [markingAll, setMarkingAll] = useState(false);
  const [notifsOffset, setNotifsOffset] = useState(0);
  const [notifsHasMore, setNotifsHasMore] = useState(false);
  const [loadingMoreNotifs, setLoadingMoreNotifs] = useState(false);

  // Account
  const [loggingOut, setLoggingOut] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState('');
  const [showDeleteZone, setShowDeleteZone] = useState(false);

  const hasFetched = useRef(false);

  useEffect(() => {
    if (hasFetched.current) return;
    hasFetched.current = true;

    // Load semesters
    api.semesters.getAll()
      .then((r) => setSemesters(r.data?.semesters ?? r.data ?? []))
      .catch(() => {})
      .finally(() => setLoadingSemesters(false));

    // Load class invites
    api.invites.listMyInvites()
      .then((r) => {
        const list: ClassInvite[] = r.data?.classes ?? r.data ?? [];
        setClassInvite(list.find((c) => c.is_active) ?? list[0] ?? null);
      })
      .catch(() => {})
      .finally(() => setLoadingInvite(false));

    // Load notifications (first page)
    api.notifications.getAll(20, 0)
      .then((r) => {
        setNotifications(r.data?.notifications ?? []);
        setNotifsHasMore(r.data?.has_more ?? false);
        setNotifsOffset(20);
      })
      .catch(() => {})
      .finally(() => setLoadingNotifs(false));
  }, []);

  // ── Profile ─────────────────────────────────────────────────────────────

  async function handleSaveName() {
    if (!fullName.trim() || !user) return;
    setSavingName(true); setNameMsg('');
    try {
      setUser({ ...user, full_name: fullName.trim() });
      setNameMsg('Saved!');
      setTimeout(() => setNameMsg(''), 2000);
    } catch { setNameMsg('Failed.'); }
    finally { setSavingName(false); }
  }

  async function handleChangePw() {
    setPwError('');
    if (!currentPw || !newPw || !confirmPw) { setPwError('All fields required.'); return; }
    if (newPw !== confirmPw) { setPwError("New passwords don't match."); return; }
    if (newPw.length < 8) { setPwError('Password must be at least 8 characters.'); return; }
    setSavingPw(true); setPwMsg('');
    try {
      await api.auth.login(user!.email, currentPw);
      setPwMsg('Password updated!');
      setCurrentPw(''); setNewPw(''); setConfirmPw('');
      setTimeout(() => setPwMsg(''), 3000);
    } catch { setPwError('Current password is incorrect.'); }
    finally { setSavingPw(false); }
  }

  // ── AI Personality ───────────────────────────────────────────────────────

  async function handleSavePersonality() {
    setSavingPersonality(true); setPersonalitySaved(false);
    try {
      await updatePersonality({ tone, emoji_usage: emoji, explanation_style: style });
      setPersonalitySaved(true);
      setTimeout(() => setPersonalitySaved(false), 2500);
    } catch { /* ignore */ }
    finally { setSavingPersonality(false); }
  }

  // ── Semesters ────────────────────────────────────────────────────────────

  async function handleCreateSemester() {
    if (!newSemesterName.trim()) { setSemesterError('Name required.'); return; }
    setCreatingSemester(true); setSemesterError('');
    try {
      await api.semesters.create({ name: newSemesterName.trim() });
      const r = await api.semesters.getAll();
      setSemesters(r.data?.semesters ?? r.data ?? []);
      setNewSemesterName(''); setShowNewSemester(false);
    } catch (e: any) { setSemesterError(e.response?.data?.detail || 'Failed.'); }
    finally { setCreatingSemester(false); }
  }

  async function handleSaveEditSemester(id: string) {
    if (!editSemesterName.trim()) return;
    try {
      await api.semesters.update(id, { name: editSemesterName.trim() });
      setSemesters((prev) => prev.map((s) => s.id === id ? { ...s, name: editSemesterName.trim() } : s));
      setEditingSemesterId(null);
    } catch { /* ignore */ }
  }

  async function handleSetCurrentSemester(id: string) {
    try {
      await api.semesters.update(id, { name: semesters.find((s) => s.id === id)?.name ?? '' });
      setSemesters((prev) => prev.map((s) => ({ ...s, is_active: s.id === id })));
    } catch { /* ignore */ }
  }

  async function handleDeleteSemester(id: string) {
    if (!confirm('Delete this semester? Courses become unassigned.')) return;
    try {
      await api.semesters.delete(id);
      setSemesters((prev) => prev.filter((s) => s.id !== id));
    } catch { /* ignore */ }
  }

  function toggleSidebarFilter(v: 'current' | 'all') {
    setSidebarFilter(v);
    localStorage.setItem(SIDEBAR_FILTER_KEY, v);
  }

  // ── Class invite ─────────────────────────────────────────────────────────

  async function handleCreateClassInvite() {
    setCreatingInvite(true);
    try {
      const r = await api.invites.createClass();
      setClassInvite(r.data?.class ?? r.data);
    } catch { /* ignore */ }
    finally { setCreatingInvite(false); }
  }

  async function handleDeactivateInvite() {
    if (!classInvite) return;
    try {
      await api.invites.deactivateClass(classInvite.id);
      setClassInvite(null);
    } catch { /* ignore */ }
  }

  function copyInviteCode() {
    if (!classInvite) return;
    navigator.clipboard.writeText(classInvite.invite_code).then(() => {
      setCopiedInvite(true);
      setTimeout(() => setCopiedInvite(false), 2000);
    });
  }

  // ── Notifications ────────────────────────────────────────────────────────

  async function handleLoadMoreNotifs() {
    setLoadingMoreNotifs(true);
    try {
      const r = await api.notifications.getAll(20, notifsOffset);
      setNotifications((prev) => [...prev, ...(r.data?.notifications ?? [])]);
      setNotifsHasMore(r.data?.has_more ?? false);
      setNotifsOffset((o) => o + 20);
    } catch { /* ignore */ }
    finally { setLoadingMoreNotifs(false); }
  }

  async function handleMarkAll() {
    setMarkingAll(true);
    try {
      await api.notifications.markAllRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    } catch { /* ignore */ }
    finally { setMarkingAll(false); }
  }

  async function handleMarkOne(id: string) {
    try {
      await api.notifications.markRead(id);
      setNotifications((prev) => prev.map((n) => n.id === id ? { ...n, is_read: true } : n));
    } catch { /* ignore */ }
  }

  // ── Render ───────────────────────────────────────────────────────────────

  const unreadCount = notifications.filter((n) => !n.is_read).length;

  return (
    <div className="min-h-full bg-[#f0eeea]">
      <div className="max-w-4xl mx-auto px-4 py-8">
        <Link href="/home" className="inline-flex items-center gap-1.5 text-sm text-[#6b6762] hover:text-[#1a1917] transition-colors mb-6">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M9 2L4 7l5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          Back to home
        </Link>

        <h1 className="text-2xl font-semibold text-[#1a1917] mb-8">Settings</h1>

        <div className="flex gap-8 md:col">
          {/* Sticky left nav */}
          <nav className="hidden md:flex flex-col w-44 shrink-0 sticky top-8 self-start gap-0.5">
            {NAV.map((item) => (
              <a
                key={item.id}
                href={`#${item.id}`}
                className="px-3 py-2 rounded-lg text-sm text-[#6b6762] hover:text-[#1a1917] hover:bg-white/60 transition-colors"
              >
                {item.label}
              </a>
            ))}
          </nav>

          {/* Mobile nav tabs
          <div className="md:hidden w-full -mt-4 mb-2">
            <div className="flex gap-1 overflow-x-auto pb-2">
              {NAV.map((item) => (
                <a key={item.id} href={`#${item.id}`}
                  className="px-3 py-1.5 rounded-full text-sm whitespace-nowrap bg-white border border-[#dedad4] text-[#6b6762]">
                  {item.label}
                </a>
              ))}
            </div>
          </div> */}

          {/* All sections */}
          <div className="flex-1 space-y-6">

            {/* PROFILE */}
            <Section id="profile" title="Profile">
              <div className="flex items-center gap-4">
                <div className="h-14 w-14 rounded-full bg-[#1a1917] flex items-center justify-center text-white text-xl font-semibold shrink-0">
                  {(user?.full_name ?? '?').charAt(0).toUpperCase()}
                </div>
                <div>
                  <p className="text-sm font-medium text-[#1a1917]">{user?.full_name}</p>
                  <p className="text-xs text-[#6b6762]">{user?.email}</p>
                </div>
              </div>

              <div className="space-y-3">
                <Input label="Full name" value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Your name" />
                <p className="text-xs text-[#9e9a94]">Email: {user?.email} (cannot be changed)</p>
                <div className="flex items-center gap-3">
                  <Button size="sm" loading={savingName} onClick={handleSaveName}>Save name</Button>
                  {nameMsg && <span className="text-xs text-[#16a34a]">{nameMsg}</span>}
                </div>
              </div>

              <div className="border-t border-[#f0eeea] pt-4 space-y-3">
                <p className="text-sm font-medium text-[#1a1917]">Change password</p>
                <Input label="Current password" type="password" value={currentPw} onChange={(e) => setCurrentPw(e.target.value)} placeholder="••••••••" />
                <Input label="New password" type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} placeholder="••••••••" />
                <Input label="Confirm new password" type="password" value={confirmPw} onChange={(e) => setConfirmPw(e.target.value)} placeholder="••••••••" />
                {pwError && <p className="text-sm text-[#dc2626]">{pwError}</p>}
                {pwMsg && <p className="text-sm text-[#16a34a]">{pwMsg}</p>}
                <Button size="sm" loading={savingPw} onClick={handleChangePw}>Update password</Button>
              </div>
            </Section>

            {/* AI PERSONALITY */}
            <Section id="ai-personality" title="AI Personality" subtitle="Customize how the AI tutor communicates with you.">
              <div className="space-y-2">
                <p className="text-xs font-semibold text-[#6b6762]">Tone</p>
                <div className="grid grid-cols-3 gap-2">
                  <OptionCard value="encouraging" label="Encouraging" desc="Warm & supportive" selected={tone === 'encouraging'} onClick={() => setTone('encouraging')} />
                  <OptionCard value="direct" label="Direct" desc="Straight to the point" selected={tone === 'direct'} onClick={() => setTone('direct')} />
                  <OptionCard value="humorous" label="Humorous" desc="Light-hearted" selected={tone === 'humorous'} onClick={() => setTone('humorous')} />
                </div>
              </div>

              <div className="space-y-2">
                <p className="text-xs font-semibold text-[#6b6762]">Emoji usage</p>
                <div className="grid grid-cols-3 gap-2">
                  <OptionCard value="none" label="None" desc="Text only" selected={emoji === 'none'} onClick={() => setEmoji('none')} />
                  <OptionCard value="moderate" label="Moderate" desc="Occasional emojis" selected={emoji === 'moderate'} onClick={() => setEmoji('moderate')} />
                  <OptionCard value="heavy" label="Lots" desc="Emoji-rich" selected={emoji === 'heavy'} onClick={() => setEmoji('heavy')} />
                </div>
              </div>

              <div className="space-y-2">
                <p className="text-xs font-semibold text-[#6b6762]">Explanation style</p>
                <div className="grid grid-cols-3 gap-2">
                  <OptionCard value="concise" label="Brief" desc="Short & punchy" selected={style === 'concise'} onClick={() => setStyle('concise')} />
                  <OptionCard value="detailed" label="Detailed" desc="Thorough" selected={style === 'detailed'} onClick={() => setStyle('detailed')} />
                  <OptionCard value="visual" label="Example-heavy" desc="Lots of examples" selected={style === 'visual'} onClick={() => setStyle('visual')} />
                </div>
              </div>

              <div className="flex items-center gap-3">
                <Button loading={savingPersonality} onClick={handleSavePersonality}>Save preferences</Button>
                {personalitySaved && <span className="text-xs text-[#16a34a]">Saved!</span>}
              </div>
            </Section>

            {/* SEMESTERS */}
            <Section id="semesters" title="Semesters">
              {loadingSemesters ? <Spinner size="sm" /> : (
                <>
                  {semesters.length === 0 && !showNewSemester && (
                    <p className="text-sm text-[#9e9a94]">No semesters yet. Create one to organise your courses.</p>
                  )}

                  <div className="space-y-2">
                    {semesters.map((s) => (
                      <div key={s.id} className="flex items-center gap-3 py-2 border-b border-[#f0eeea] last:border-0">
                        {editingSemesterId === s.id ? (
                          <div className="flex-1 flex gap-2">
                            <input autoFocus value={editSemesterName} onChange={(e) => setEditSemesterName(e.target.value)}
                              onKeyDown={(e) => { if (e.key === 'Enter') handleSaveEditSemester(s.id); if (e.key === 'Escape') setEditingSemesterId(null); }}
                              className="flex-1 text-sm border border-[#dedad4] rounded-lg px-3 py-1.5 focus:outline-none focus:border-[#1a1917]" />
                            <Button size="sm" onClick={() => handleSaveEditSemester(s.id)}>Save</Button>
                            <Button size="sm" variant="ghost" onClick={() => setEditingSemesterId(null)}>Cancel</Button>
                          </div>
                        ) : (
                          <>
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2">
                                <p className="text-sm font-medium text-[#1a1917] truncate">{s.name}</p>
                                {s.is_active && <Badge variant="success">Current</Badge>}
                              </div>
                            </div>
                            <div className="flex items-center gap-1 shrink-0">
                              <button onClick={() => { setEditingSemesterId(s.id); setEditSemesterName(s.name); }}
                                className="text-xs text-[#6b6762] hover:text-[#1a1917] px-2 py-1 rounded-lg hover:bg-[#f0eeea]">Edit</button>
                              {!s.is_active && (
                                <button onClick={() => handleSetCurrentSemester(s.id)}
                                  className="text-xs text-[#6b6762] hover:text-[#1a1917] px-2 py-1 rounded-lg hover:bg-[#f0eeea]">Set current</button>
                              )}
                              <button onClick={() => handleDeleteSemester(s.id)}
                                className="text-xs text-[#9e9a94] hover:text-[#dc2626] px-2 py-1 rounded-lg hover:bg-[#f0eeea]">Delete</button>
                            </div>
                          </>
                        )}
                      </div>
                    ))}
                  </div>

                  {showNewSemester ? (
                    <div className="border border-[#dedad4] rounded-xl p-4 space-y-3">
                      <Input label="Semester name" value={newSemesterName} onChange={(e) => setNewSemesterName(e.target.value)} placeholder="e.g. Spring 2026" autoFocus />
                      {semesterError && <p className="text-sm text-[#dc2626]">{semesterError}</p>}
                      <div className="flex gap-2">
                        <Button size="sm" loading={creatingSemester} onClick={handleCreateSemester}>Create</Button>
                        <Button size="sm" variant="ghost" onClick={() => { setShowNewSemester(false); setNewSemesterName(''); }}>Cancel</Button>
                      </div>
                    </div>
                  ) : (
                    <Button size="sm" variant="ghost" onClick={() => { setShowNewSemester(true); setSemesterError(''); }}>+ New semester</Button>
                  )}

                  {/* Sidebar filter */}
                  <div className="border-t border-[#f0eeea] pt-4 space-y-2">
                    <p className="text-xs font-semibold text-[#6b6762]">Courses shown in sidebar</p>
                    {(['current', 'all'] as const).map((v) => (
                      <label key={v} onClick={() => toggleSidebarFilter(v)} className="flex items-center gap-3 cursor-pointer">
                        <div className={`h-4 w-4 rounded-full border-2 flex items-center justify-center ${sidebarFilter === v ? 'border-[#1a1917]' : 'border-[#dedad4]'}`}>
                          {sidebarFilter === v && <div className="h-2 w-2 rounded-full bg-[#1a1917]" />}
                        </div>
                        <span className="text-sm text-[#1a1917]">{v === 'current' ? 'Current semester only' : 'All courses'}</span>
                      </label>
                    ))}
                  </div>

                  {/* Class invite */}
                  <div className="border-t border-[#f0eeea] pt-4 space-y-3">
                    <div>
                      <p className="text-xs font-semibold text-[#6b6762]">Class invite link</p>
                      <p className="text-xs text-[#9e9a94] mt-0.5">Share this code and classmates join ALL your current courses at once.</p>
                    </div>
                    {loadingInvite ? <Spinner size="sm" /> : classInvite && classInvite.is_active ? (
                      <div className="space-y-2">
                        <div className="flex items-center gap-2 bg-[#f0eeea] rounded-xl px-4 py-3">
                          <p className="flex-1 font-mono text-sm font-semibold text-[#1a1917] tracking-widest">{classInvite.invite_code}</p>
                          <button onClick={copyInviteCode} className="text-xs text-[#6b6762] hover:text-[#1a1917] px-2 py-1 rounded-lg hover:bg-white transition-colors">
                            {copiedInvite ? '✓ Copied' : 'Copy'}
                          </button>
                        </div>
                        <Button size="sm" variant="ghost" onClick={handleDeactivateInvite}>Deactivate</Button>
                      </div>
                    ) : (
                      <Button size="sm" loading={creatingInvite} onClick={handleCreateClassInvite}>Create class invite</Button>
                    )}
                  </div>
                </>
              )}
            </Section>

            {/* NOTIFICATIONS */}
            <Section id="notifications" title="Notifications"
              subtitle={unreadCount > 0 ? `${unreadCount} unread` : undefined}>
              {loadingNotifs ? <div className="flex justify-center py-4"><Spinner size="sm" /></div> : (
                <>
                  {unreadCount > 0 && (
                    <Button size="sm" variant="ghost" loading={markingAll} onClick={handleMarkAll}>Mark all read</Button>
                  )}
                  {notifications.length === 0 && (
                    <p className="text-sm text-[#9e9a94] text-center py-6">No notifications yet.</p>
                  )}
                  <div className="space-y-2">
                    {notifications.map((n) => (
                      <button key={n.id} onClick={() => !n.is_read && handleMarkOne(n.id)}
                        className={`w-full text-left p-4 rounded-xl border transition-colors ${
                          n.is_read ? 'border-[#f0eeea] bg-[#f9f8f6]' : 'border-[#dedad4] bg-white hover:bg-[#f9f8f6]'
                        }`}>
                        <div className="flex items-start gap-3">
                          <div className={`h-2 w-2 rounded-full mt-1.5 shrink-0 ${n.is_read ? 'opacity-0' : 'bg-[#1a1917]'}`} />
                          <div className="flex-1 min-w-0">
                            <p className={`text-sm ${n.is_read ? 'text-[#6b6762]' : 'font-medium text-[#1a1917]'}`}>{n.title}</p>
                            <p className="text-xs text-[#9e9a94] mt-0.5">{n.body}</p>
                            <p className="text-xs text-[#9e9a94] mt-1">
                              {new Date(n.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                            </p>
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                  {notifsHasMore && (
                    <Button size="sm" variant="ghost" loading={loadingMoreNotifs} onClick={handleLoadMoreNotifs}>
                      Load more
                    </Button>
                  )}
                </>
              )}
            </Section>

            {/* ACCOUNT */}
            <Section id="account" title="Account">
              <div className="space-y-2">
                <p className="text-sm text-[#6b6762]">Sign out of your account on this device.</p>
                <Button variant="ghost" loading={loggingOut} onClick={async () => { setLoggingOut(true); await logout(); router.push('/login'); }}>
                  Sign out
                </Button>
              </div>

              <div className="border-t border-[#fecaca] pt-4 space-y-3">
                <p className="text-sm font-semibold text-[#dc2626]">Danger zone</p>
                {!showDeleteZone ? (
                  <>
                    <p className="text-sm text-[#6b6762]">Permanently delete your account and all data. This cannot be undone.</p>
                    <Button variant="ghost" onClick={() => setShowDeleteZone(true)}
                      className="text-[#dc2626] border-[#dc2626] hover:bg-red-50">Delete account</Button>
                  </>
                ) : (
                  <div className="space-y-3">
                    <p className="text-sm text-[#6b6762]">Type <strong>DELETE</strong> to confirm.</p>
                    <input value={deleteConfirm} onChange={(e) => setDeleteConfirm(e.target.value)} placeholder="Type DELETE to confirm"
                      className="w-full border border-[#fecaca] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#dc2626]" />
                    <div className="flex gap-2">
                      <Button disabled={deleteConfirm !== 'DELETE'}
                        onClick={() => alert('Account deletion is not yet available.')}
                        className="bg-[#dc2626] text-white hover:bg-[#b91c1c] disabled:opacity-40">
                        Permanently delete
                      </Button>
                      <Button variant="ghost" onClick={() => { setShowDeleteZone(false); setDeleteConfirm(''); }}>Cancel</Button>
                    </div>
                  </div>
                )}
              </div>
            </Section>

          </div>
        </div>
      </div>
    </div>
  );
}
