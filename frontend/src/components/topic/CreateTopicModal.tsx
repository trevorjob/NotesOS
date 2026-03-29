'use client';

import { useRef, useState } from 'react';
import { api } from '@/lib/api';
import { useCourseStore } from '@/stores/courses';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';

interface CreateTopicModalProps {
  isOpen: boolean;
  courseId: string;
  onClose: () => void;
  onCreated: (topicId: string) => void;
}

type Tab = 'files' | 'text';
type Phase = 'idle' | 'creating' | 'uploading';

export function CreateTopicModal({ isOpen, courseId, onClose, onCreated }: CreateTopicModalProps) {
  const { courses } = useCourseStore();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [title, setTitle] = useState('');
  const [tab, setTab] = useState<Tab>('files');

  // File state
  const [files, setFiles] = useState<File[]>([]);
  const [fileTitle, setFileTitle] = useState('');

  // Text state
  const [textTitle, setTextTitle] = useState('');
  const [textContent, setTextContent] = useState('');

  const [phase, setPhase] = useState<Phase>('idle');
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState('');

  const busy = phase !== 'idle';

  function reset() {
    setTitle(''); setTab('files');
    setFiles([]); setFileTitle('');
    setTextTitle(''); setTextContent('');
    setPhase('idle'); setProgress(0); setError('');
  }

  function handleClose() {
    if (busy) return;
    reset();
    onClose();
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files) setFiles(Array.from(e.target.files));
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setFiles((prev) => [...prev, ...Array.from(e.dataTransfer.files)]);
  }

  function removeFile(i: number) {
    setFiles((prev) => prev.filter((_, idx) => idx !== i));
  }

  const hasResources = tab === 'files' ? files.length > 0 : textContent.trim().length > 0;

  async function handleCreate() {
    if (!title.trim()) { setError('Topic title is required.'); return; }
    setError('');

    const course = courses.find((c) => c.id === courseId);
    const orderIndex = (course?.topics?.length ?? 0) + 1;

    // Step 1: Create the topic directly via API to get a reliable topicId
    // (avoids the store's createTopic which runs selectCourse internally and
    //  can mask errors before we have a valid topicId for the upload)
    setPhase('creating');
    let topicId: string;
    try {
      const response = await api.topics.create(courseId, {
        title: title.trim(),
        order_index: orderIndex,
      });
      topicId = (response.data?.topic ?? response.data)?.id;
      if (!topicId) throw new Error('Topic created but no ID returned');
      // Invalidate the store so it re-fetches fresh data on navigation
      useCourseStore.getState().clearCurrentCourse();
    } catch (e: unknown) {
      setPhase('idle');
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        || (e as Error)?.message
        || 'Failed to create topic.';
      setError(msg);
      return;
    }

    // Step 2: Upload resources if provided
    if (hasResources) {
      setPhase('uploading');
      try {
        if (tab === 'files') {
          await api.resources.upload(topicId, courseId, files, fileTitle || undefined, false, setProgress);
        } else {
          await api.resources.createText(topicId, { content: textContent.trim(), title: textTitle.trim() || undefined });
        }
      } catch (e: unknown) {
        const msg = (e as { response?: { data?: { detail?: string } }; message?: string })?.response?.data?.detail
          || (e as Error)?.message
          || 'Upload failed. You can add resources from the topic page.';
        setError(msg);
        setPhase('idle');
        setTimeout(() => { reset(); onCreated(topicId); }, 3000);
        return;
      }
    }

    reset();
    onCreated(topicId);
  }

  const buttonLabel = phase === 'creating' ? 'Creating…' : phase === 'uploading' ? 'Uploading…' : 'Create';

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="New Topic">
      <div className="space-y-4">
        {/* Topic title */}
        <Input
          label="Topic Title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="e.g. Week 4 — Memory Management"
          disabled={busy}
        />

        {/* Resources section */}
        <div>
          <p className="text-xs font-medium text-[#9e9a94] mb-2 uppercase tracking-wide">Add resources (optional)</p>

          {/* Tab bar */}
          <div className="flex gap-1 bg-[#f0eeea] rounded-xl p-1 mb-3">
            {(['files', 'text'] as const).map((t) => (
              <button
                key={t}
                onClick={() => { setTab(t); setError(''); }}
                disabled={busy}
                className={`flex-1 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  tab === t ? 'bg-white text-[#1a1917] shadow-sm' : 'text-[#6b6762]'
                }`}
              >
                {t === 'files' ? 'Files' : 'Text'}
              </button>
            ))}
          </div>

          {/* Files tab */}
          {tab === 'files' && (
            <div className="space-y-3">
              <div
                onDrop={handleDrop}
                onDragOver={(e) => e.preventDefault()}
                onClick={() => !busy && fileInputRef.current?.click()}
                className="border-2 border-dashed border-[#dedad4] rounded-xl p-5 text-center cursor-pointer hover:border-[#9e9a94] transition-colors"
              >
                <p className="text-sm text-[#6b6762]">Drag & drop files or <span className="text-[#1a1917] underline">browse</span></p>
                <p className="text-xs text-[#9e9a94] mt-1">PDF, images, PNG, JPG</p>
                <input ref={fileInputRef} type="file" multiple accept=".pdf,image/*" className="hidden" onChange={handleFileChange} />
              </div>

              {files.length > 0 && (
                <ul className="space-y-1.5 max-h-28 overflow-y-auto">
                  {files.map((f, i) => (
                    <li key={i} className="flex items-center justify-between text-sm bg-[#f0eeea] rounded-lg px-3 py-2">
                      <span className="truncate flex-1 text-[#1a1917]">{f.name}</span>
                      <button onClick={() => removeFile(i)} disabled={busy} className="ml-2 text-[#9e9a94] hover:text-[#dc2626] transition-colors shrink-0">✕</button>
                    </li>
                  ))}
                </ul>
              )}

              <div>
                <label className="block text-xs font-medium text-[#6b6762] mb-1">File title (optional)</label>
                <input
                  value={fileTitle}
                  onChange={(e) => setFileTitle(e.target.value)}
                  disabled={busy}
                  placeholder="e.g. Lecture 4 slides"
                  className="w-full bg-[#f0eeea] border border-[#dedad4] rounded-lg px-3 py-2 text-sm text-[#1a1917] placeholder-[#9e9a94] focus:outline-none focus:border-[#1a1917]"
                />
              </div>
            </div>
          )}

          {/* Text tab */}
          {tab === 'text' && (
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-[#6b6762] mb-1">Title (optional)</label>
                <input
                  value={textTitle}
                  onChange={(e) => setTextTitle(e.target.value)}
                  disabled={busy}
                  placeholder="e.g. Week 3 lecture notes"
                  className="w-full bg-[#f0eeea] border border-[#dedad4] rounded-lg px-3 py-2 text-sm text-[#1a1917] placeholder-[#9e9a94] focus:outline-none focus:border-[#1a1917]"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-[#6b6762] mb-1">Content</label>
                <textarea
                  value={textContent}
                  onChange={(e) => setTextContent(e.target.value)}
                  disabled={busy}
                  placeholder="Paste your notes, type content, copy from anywhere…"
                  rows={6}
                  className="w-full resize-y bg-[#f0eeea] border border-[#dedad4] rounded-lg px-3 py-2 text-sm text-[#1a1917] placeholder-[#9e9a94] focus:outline-none focus:border-[#1a1917]"
                />
                <p className="text-xs text-[#9e9a94] mt-1">{textContent.length} characters</p>
              </div>
            </div>
          )}
        </div>

        {/* Upload progress */}
        {phase === 'uploading' && (
          <div>
            <div className="h-1.5 bg-[#e8e5e0] rounded-full overflow-hidden">
              <div className="h-1.5 bg-[#1a1917] rounded-full transition-all duration-300" style={{ width: `${progress}%` }} />
            </div>
            <p className="text-xs text-[#6b6762] mt-1">{Math.round(progress)}% uploaded…</p>
          </div>
        )}

        {error && <p className="text-sm text-[#dc2626]">{error}</p>}

        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" size="sm" onClick={handleClose} disabled={busy}>Cancel</Button>
          <Button size="sm" loading={busy} onClick={handleCreate}>{buttonLabel}</Button>
        </div>
      </div>
    </Modal>
  );
}
