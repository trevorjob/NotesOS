'use client';

import { useRef, useState } from 'react';
import { api } from '@/lib/api';
import { Modal } from '@/components/ui/Modal';
import { Button } from '@/components/ui/Button';

interface AddResourcesModalProps {
  isOpen: boolean;
  topicId: string;
  courseId: string;
  onClose: () => void;
  onAdded: () => void;
}

type Tab = 'files' | 'text';

export function AddResourcesModal({ isOpen, topicId, courseId, onClose, onAdded }: AddResourcesModalProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [tab, setTab] = useState<Tab>('files');

  // File upload state
  const [files, setFiles] = useState<File[]>([]);
  const [fileTitle, setFileTitle] = useState('');
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);

  // Text state
  const [textTitle, setTextTitle] = useState('');
  const [textContent, setTextContent] = useState('');
  const [savingText, setSavingText] = useState(false);

  const [error, setError] = useState('');

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

  async function handleUpload() {
    if (files.length === 0) { setError('Select at least one file.'); return; }
    setUploading(true); setError(''); setProgress(0);
    try {
      await api.resources.upload(topicId, courseId, files, fileTitle || undefined, false, setProgress);
      resetAndClose();
    } catch (e: unknown) {
      const error = e as { response?: { data?: { detail?: string } } } & Error;
      setError(error.response?.data?.detail || error.message || 'Upload failed.');
    } finally { setUploading(false); }
  }

  async function handleAddText() {
    if (!textContent.trim()) { setError('Content is required.'); return; }
    setSavingText(true); setError('');
    try {
      await api.resources.createText(topicId, { content: textContent.trim(), title: textTitle.trim() || undefined });
      resetAndClose();
    } catch (e: unknown) {
      const error = e as { response?: { data?: { detail?: string } } } & Error;
      setError(error.response?.data?.detail || 'Failed to save text.');
    } finally { setSavingText(false); }
  }

  function resetAndClose() {
    setFiles([]); setFileTitle(''); setTextTitle(''); setTextContent('');
    setError(''); setProgress(0);
    onAdded();
    onClose();
  }

  function handleClose() {
    if (uploading || savingText) return;
    resetAndClose();
  }

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Add Materials">
      <div className="space-y-4">
        {/* Tab bar */}
        <div className="flex gap-1 bg-[#f0eeea] rounded-xl p-1">
          {(['files', 'text'] as const).map((t) => (
            <button
              key={t}
              onClick={() => { setTab(t); setError(''); }}
              className={`flex-1 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                tab === t ? 'bg-white text-[#1a1917] shadow-sm' : 'text-[#6b6762]'
              }`}
            >
              {t === 'files' ? 'Files' : 'Text'}
            </button>
          ))}
        </div>

        {/* FILES TAB */}
        {tab === 'files' && (
          <>
            <div
              onDrop={handleDrop}
              onDragOver={(e) => e.preventDefault()}
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-[#dedad4] rounded-xl p-6 text-center cursor-pointer hover:border-[#9e9a94] transition-colors"
            >
              <p className="text-sm text-[#6b6762]">Drag & drop files or <span className="text-[#1a1917] underline">browse</span></p>
              <p className="text-xs text-[#9e9a94] mt-1">PDF, images, PNG, JPG</p>
              <input ref={fileInputRef} type="file" multiple accept=".pdf,image/*" className="hidden" onChange={handleFileChange} />
            </div>

            {files.length > 0 && (
              <ul className="space-y-1.5 max-h-36 overflow-y-auto">
                {files.map((f, i) => (
                  <li key={i} className="flex items-center justify-between text-sm bg-[#f0eeea] rounded-lg px-3 py-2">
                    <span className="truncate flex-1 text-[#1a1917]">{f.name}</span>
                    <button onClick={() => removeFile(i)} className="ml-2 text-[#9e9a94] hover:text-[#dc2626] transition-colors shrink-0">✕</button>
                  </li>
                ))}
              </ul>
            )}

            <div>
              <label className="block text-xs font-medium text-[#6b6762] mb-1">Title (optional)</label>
              <input
                value={fileTitle}
                onChange={(e) => setFileTitle(e.target.value)}
                placeholder="e.g. Lecture 4 slides"
                className="w-full bg-[#f0eeea] border border-[#dedad4] rounded-lg px-3 py-2 text-sm text-[#1a1917] placeholder-[#9e9a94] focus:outline-none focus:border-[#1a1917]"
              />
            </div>

            {uploading && (
              <div>
                <div className="h-1.5 bg-[#e8e5e0] rounded-full overflow-hidden">
                  <div className="h-1.5 bg-[#1a1917] rounded-full transition-all duration-300" style={{ width: `${progress}%` }} />
                </div>
                <p className="text-xs text-[#6b6762] mt-1">{Math.round(progress)}% uploaded…</p>
              </div>
            )}

            {error && <p className="text-sm text-[#dc2626]">{error}</p>}

            <div className="flex justify-end gap-2 pt-1">
              <Button variant="ghost" size="sm" onClick={handleClose} disabled={uploading}>Cancel</Button>
              <Button size="sm" loading={uploading} onClick={handleUpload}>Upload</Button>
            </div>
          </>
        )}

        {/* TEXT TAB */}
        {tab === 'text' && (
          <>
            <div>
              <label className="block text-xs font-medium text-[#6b6762] mb-1">Title (optional)</label>
              <input
                value={textTitle}
                onChange={(e) => setTextTitle(e.target.value)}
                placeholder="e.g. Week 3 lecture notes"
                className="w-full bg-[#f0eeea] border border-[#dedad4] rounded-lg px-3 py-2 text-sm text-[#1a1917] placeholder-[#9e9a94] focus:outline-none focus:border-[#1a1917]"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-[#6b6762] mb-1">Content *</label>
              <textarea
                value={textContent}
                onChange={(e) => setTextContent(e.target.value)}
                placeholder="Paste your notes, type content, copy from anywhere…"
                rows={8}
                className="w-full resize-y bg-[#f0eeea] border border-[#dedad4] rounded-lg px-3 py-2 text-sm text-[#1a1917] placeholder-[#9e9a94] focus:outline-none focus:border-[#1a1917]"
              />
              <p className="text-xs text-[#9e9a94] mt-1">{textContent.length} characters</p>
            </div>

            {error && <p className="text-sm text-[#dc2626]">{error}</p>}

            <div className="flex justify-end gap-2 pt-1">
              <Button variant="ghost" size="sm" onClick={handleClose}>Cancel</Button>
              <Button size="sm" loading={savingText} onClick={handleAddText}>Add resource</Button>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
