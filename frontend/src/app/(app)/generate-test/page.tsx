'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useCourseStore } from '@/stores/courses';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';

type QuestionType = 'mixed' | 'mcq' | 'short_answer';
type Difficulty = 'easy' | 'medium' | 'hard';

const QUESTION_COUNT_PRESETS = [5, 10, 20, 50];

export default function GenerateTestPage() {
  return (
    <Suspense fallback={<div className="flex justify-center items-center min-h-[50vh]"><Spinner /></div>}>
      <GenerateTestPageInner />
    </Suspense>
  );
}

function GenerateTestPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const paramCourseId = searchParams.get('courseId') ?? '';
  const paramTopicId = searchParams.get('topicId') ?? '';
  const { courses, fetchCourses, selectCourse } = useCourseStore();

  const [selectedCourseId, setSelectedCourseId] = useState(paramCourseId);
  const [topics, setTopics] = useState<Array<{ id: string; title: string }>>([]);
  const [selectedTopicIds, setSelectedTopicIds] = useState<Set<string>>(
    paramTopicId ? new Set([paramTopicId]) : new Set()
  );
  const [loadingTopics, setLoadingTopics] = useState(false);

  const [questionCount, setQuestionCount] = useState(10);
  const [customCount, setCustomCount] = useState('');
  const [useCustom, setUseCustom] = useState(false);
  const [questionType, setQuestionType] = useState<QuestionType>('mixed');
  const [difficulty, setDifficulty] = useState<Difficulty>('medium');

  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState('');

  const [pastTests, setPastTests] = useState<Array<{ id: string; title: string; question_count: number; created_at: string }>>([]);
  const [loadingPastTests, setLoadingPastTests] = useState(false);
  const [copiedTestId, setCopiedTestId] = useState<string | null>(null);

  useEffect(() => {
    fetchCourses();
  }, [fetchCourses]);

  useEffect(() => {
    if (courses.length > 0 && !selectedCourseId) {
      setSelectedCourseId(paramCourseId || courses[0].id);
    }
  }, [courses, selectedCourseId, paramCourseId]);

  useEffect(() => {
    if (!selectedCourseId) return;
    loadTopics(selectedCourseId, !!paramTopicId);
    // Load shared tests for this course
    setLoadingPastTests(true);
    api.ai.listTests(selectedCourseId)
      .then((res) => setPastTests(res.data ?? []))
      .catch(() => {})
      .finally(() => setLoadingPastTests(false));
  }, [selectedCourseId]);

  async function loadTopics(courseId: string, keepSelection = false) {
    setLoadingTopics(true);
    if (!keepSelection) setSelectedTopicIds(new Set());
    try {
      await selectCourse(courseId);
      const course = useCourseStore.getState().courses.find((c) => c.id === courseId);
      const t = course?.topics ?? [];
      setTopics(t);
      if (!keepSelection) setSelectedTopicIds(new Set(t.map((x) => x.id)));
    } catch { /* ignore */ }
    finally { setLoadingTopics(false); }
  }

  function toggleTopic(id: string) {
    setSelectedTopicIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function selectAll() { setSelectedTopicIds(new Set(topics.map((t) => t.id))); }
  function deselectAll() { setSelectedTopicIds(new Set()); }

  function shareTest(testId: string) {
    const url = `${window.location.origin}/tests/${testId}`;
    navigator.clipboard.writeText(url);
    setCopiedTestId(testId);
    setTimeout(() => setCopiedTestId(null), 2000);
  }

  const finalCount = useCustom ? (parseInt(customCount) || 10) : questionCount;

  async function handleGenerate() {
    if (selectedTopicIds.size === 0) { setError('Select at least one topic.'); return; }
    if (finalCount < 1 || finalCount > 100) { setError('Question count must be between 1 and 100.'); return; }
    setGenerating(true); setError('');

    const typeMap: Record<QuestionType, string[]> = {
      mixed: ['mcq', 'short_answer'],
      mcq: ['mcq'],
      short_answer: ['short_answer'],
    };

    try {
      const res = await api.ai.generateTest(selectedCourseId, {
        topic_ids: Array.from(selectedTopicIds),
        question_count: finalCount,
        difficulty,
        question_types: typeMap[questionType],
      });
      const test = res.data?.test ?? res.data;
      router.push(`/tests/${test.id}`);
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || 'Failed to generate test. Please try again.');
      setGenerating(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-[#1a1917]">Generate Practice Test</h1>
        <p className="text-sm text-[#6b6762] mt-1">Customise a test across one or multiple topics.</p>
      </div>

      {/* Course selector */}
      <div className="bg-white rounded-2xl border border-[#dedad4] p-5 space-y-3">
        <label className="text-xs font-semibold text-[#6b6762] uppercase tracking-wide">Course</label>
        {courses.length === 0 ? (
          <p className="text-sm text-[#9e9a94]">No courses yet.</p>
        ) : (
          <select
            value={selectedCourseId}
            onChange={(e) => setSelectedCourseId(e.target.value)}
            className="w-full bg-[#f0eeea] border border-[#dedad4] rounded-lg px-3 py-2 text-sm text-[#1a1917] focus:outline-none focus:border-[#1a1917]"
          >
            {courses.map((c) => (
              <option key={c.id} value={c.id}>{c.code} — {c.name}</option>
            ))}
          </select>
        )}
      </div>

      {/* Topics */}
      <div className="bg-white rounded-2xl border border-[#dedad4] p-5 space-y-3">
        <div className="flex items-center justify-between">
          <label className="text-xs font-semibold text-[#6b6762] uppercase tracking-wide">Topics</label>
          <div className="flex gap-3">
            <button onClick={selectAll} className="text-xs text-[#6b6762] hover:text-[#1a1917] transition-colors">Select all</button>
            <button onClick={deselectAll} className="text-xs text-[#6b6762] hover:text-[#1a1917] transition-colors">Deselect all</button>
          </div>
        </div>

        {loadingTopics ? (
          <div className="flex justify-center py-4"><Spinner size="sm" /></div>
        ) : topics.length === 0 ? (
          <p className="text-sm text-[#9e9a94]">No topics in this course yet.</p>
        ) : (
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {topics.map((t) => {
              const checked = selectedTopicIds.has(t.id);
              return (
                <label key={t.id} className="flex items-center gap-3 cursor-pointer group">
                  <div
                    onClick={() => toggleTopic(t.id)}
                    className={`h-4 w-4 rounded border-2 flex items-center justify-center transition-colors ${
                      checked ? 'border-[#1a1917] bg-[#1a1917]' : 'border-[#dedad4] group-hover:border-[#9e9a94]'
                    }`}
                  >
                    {checked && (
                      <svg width="8" height="6" viewBox="0 0 8 6" fill="none">
                        <path d="M1 3l2 2 4-4" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    )}
                  </div>
                  <span className="text-sm text-[#1a1917]">{t.title}</span>
                </label>
              );
            })}
          </div>
        )}
        {selectedTopicIds.size > 0 && (
          <p className="text-xs text-[#9e9a94]">{selectedTopicIds.size} topic{selectedTopicIds.size !== 1 ? 's' : ''} selected</p>
        )}
      </div>

      {/* Question count */}
      <div className="bg-white rounded-2xl border border-[#dedad4] p-5 space-y-3">
        <label className="text-xs font-semibold text-[#6b6762] uppercase tracking-wide">Number of questions</label>
        <div className="flex flex-wrap gap-2">
          {QUESTION_COUNT_PRESETS.map((n) => (
            <button
              key={n}
              onClick={() => { setQuestionCount(n); setUseCustom(false); }}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors border ${
                !useCustom && questionCount === n
                  ? 'bg-[#1a1917] text-white border-[#1a1917]'
                  : 'border-[#dedad4] text-[#1a1917] hover:border-[#9e9a94]'
              }`}
            >
              {n}
            </button>
          ))}
          <div className="flex items-center gap-2">
            <button
              onClick={() => setUseCustom(true)}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors border ${
                useCustom ? 'bg-[#1a1917] text-white border-[#1a1917]' : 'border-[#dedad4] text-[#1a1917] hover:border-[#9e9a94]'
              }`}
            >
              Custom
            </button>
            {useCustom && (
              <input
                autoFocus
                type="number"
                min={1}
                max={100}
                value={customCount}
                onChange={(e) => setCustomCount(e.target.value)}
                placeholder="e.g. 30"
                className="w-20 border border-[#dedad4] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#1a1917]"
              />
            )}
          </div>
        </div>
      </div>

      {/* Question type + difficulty */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white rounded-2xl border border-[#dedad4] p-5 space-y-3">
          <label className="text-xs font-semibold text-[#6b6762] uppercase tracking-wide">Type</label>
          <div className="space-y-1.5">
            {([['mixed', 'Mixed'], ['mcq', 'MCQ only'], ['short_answer', 'Short answer only']] as const).map(([v, l]) => (
              <label key={v} className="flex items-center gap-2.5 cursor-pointer">
                <div onClick={() => setQuestionType(v)} className={`h-4 w-4 rounded-full border-2 flex items-center justify-center ${questionType === v ? 'border-[#1a1917]' : 'border-[#dedad4]'}`}>
                  {questionType === v && <div className="h-2 w-2 rounded-full bg-[#1a1917]" />}
                </div>
                <span className="text-sm text-[#1a1917]">{l}</span>
              </label>
            ))}
          </div>
        </div>

        <div className="bg-white rounded-2xl border border-[#dedad4] p-5 space-y-3">
          <label className="text-xs font-semibold text-[#6b6762] uppercase tracking-wide">Difficulty</label>
          <div className="space-y-1.5">
            {([['easy', 'Easy'], ['medium', 'Medium'], ['hard', 'Hard']] as const).map(([v, l]) => (
              <label key={v} className="flex items-center gap-2.5 cursor-pointer">
                <div onClick={() => setDifficulty(v)} className={`h-4 w-4 rounded-full border-2 flex items-center justify-center ${difficulty === v ? 'border-[#1a1917]' : 'border-[#dedad4]'}`}>
                  {difficulty === v && <div className="h-2 w-2 rounded-full bg-[#1a1917]" />}
                </div>
                <span className="text-sm text-[#1a1917]">{l}</span>
              </label>
            ))}
          </div>
        </div>
      </div>

      {error && <p className="text-sm text-[#dc2626]">{error}</p>}

      <Button
        className="w-full"
        loading={generating}
        onClick={handleGenerate}
        disabled={selectedTopicIds.size === 0 || generating}
      >
        {generating ? 'Generating…' : `Generate ${useCustom ? (parseInt(customCount) || '?') : questionCount}-question test`}
      </Button>

      {generating && (
        <p className="text-xs text-center text-[#9e9a94]">
          Generating questions using your materials… this may take 10–20 seconds.
        </p>
      )}

      {/* Past tests — shared course resource */}
      <div className="space-y-3">
        <h2 className="text-sm font-semibold text-[#6b6762] uppercase tracking-wide">Past Tests</h2>
        {loadingPastTests && <div className="flex justify-center py-4"><Spinner size="sm" /></div>}
        {!loadingPastTests && pastTests.length === 0 && (
          <p className="text-sm text-[#9e9a94]">No tests generated for this course yet.</p>
        )}
        {!loadingPastTests && pastTests.length > 0 && (
          <div className="space-y-2">
            {pastTests.map((t) => (
              <div
                key={t.id}
                className="bg-white border border-[#dedad4] rounded-xl px-4 py-3 flex items-center justify-between gap-3"
              >
                <div>
                  <p className="text-sm font-medium text-[#1a1917]">{t.title}</p>
                  <p className="text-xs text-[#9e9a94]">
                    {t.question_count} questions ·{' '}
                    {new Date(t.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => shareTest(t.id)}
                    className="text-xs text-[#9e9a94] hover:text-[#1a1917] transition-colors px-2 py-1 rounded-lg hover:bg-[#f0eeea]"
                    title="Copy link"
                  >
                    {copiedTestId === t.id ? 'Copied!' : 'Share'}
                  </button>
                  <Button size="sm" variant="ghost" onClick={() => router.push(`/tests/${t.id}`)}>
                    Take
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
