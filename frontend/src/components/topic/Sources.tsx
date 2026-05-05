'use client';

import { useState } from 'react';
import { Collapsible } from '@/components/ui/Collapsible';
import { SourceViewer, ViewerFile } from '@/components/ui/SourceViewer';

export interface Resource {
  id: string;
  title: string;
  resource_type: string;
  file_url?: string;
  files?: Array<{ id: string; file_url: string; file_order: number }>;
  created_at: string;
}

function TypeLabel({ type }: { type: string }) {
  const map: Record<string, string> = {
    pdf: 'PDF',
    image: 'Image',
    text: 'Text',
    handwritten: 'Handwritten',
  };
  return <span className="text-xs text-[#9e9a94] uppercase tracking-wide">{map[type] ?? type}</span>;
}

interface SourcesProps {
  resources: Resource[];
}

export function Sources({ resources }: SourcesProps) {
  const [viewerFiles, setViewerFiles] = useState<ViewerFile[]>([]);
  const [viewerIndex, setViewerIndex] = useState(0);
  const [viewerOpen, setViewerOpen] = useState(false);

  function openViewer(files: ViewerFile[], startIndex: number) {
    setViewerFiles(files);
    setViewerIndex(startIndex);
    setViewerOpen(true);
  }

  if (resources.length === 0) return null;

  return (
    <>
      <Collapsible title="Sources" count={resources.length} storageKey="sources-section">
        <div className="space-y-3">
          {resources.map((r) => {
            const type = r.resource_type?.toLowerCase();
            const isImage = type === 'image' || type === 'handwritten';
            const imageFiles = r.files && r.files.length > 0 ? r.files : null;

            // Build ViewerFile list for this resource
            const viewerFilesForResource: ViewerFile[] = imageFiles
              ? imageFiles.map((f, i) => ({
                  id: f.id,
                  url: f.file_url,
                  type: 'image' as const,
                  label: imageFiles.length > 1 ? `${r.title || 'Untitled'} (${i + 1}/${imageFiles.length})` : (r.title || 'Untitled'),
                }))
              : r.file_url
              ? [{ id: r.id, url: r.file_url, type: 'pdf' as const, label: r.title || 'Untitled' }]
              : [];

            return (
              <div key={r.id} className="flex items-start gap-3">
                {/* Image thumbnails */}
                {isImage && imageFiles ? (
                  <div className="flex gap-1.5 shrink-0 flex-wrap">
                    {imageFiles.slice(0, 3).map((f, i) => (
                      <button
                        key={f.id}
                        onClick={() => openViewer(viewerFilesForResource, i)}
                        className="focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 rounded-lg"
                      >
                        <img
                          src={f.file_url}
                          alt={r.title || 'Resource'}
                          className="h-16 w-16 rounded-lg object-cover border border-[#dedad4] hover:opacity-90 transition-opacity cursor-zoom-in"
                        />
                      </button>
                    ))}
                    {imageFiles.length > 3 && (
                      <button
                        onClick={() => openViewer(viewerFilesForResource, 3)}
                        className="h-16 w-16 rounded-lg bg-[#f0eeea] border border-[#dedad4] flex items-center justify-center text-xs text-[#6b6762] hover:bg-[#e8e5df] transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500"
                      >
                        +{imageFiles.length - 3}
                      </button>
                    )}
                  </div>
                ) : (
                  <div className="h-10 w-10 rounded-lg bg-[#f0eeea] border border-[#dedad4] flex items-center justify-center shrink-0 text-lg">
                    {type === 'pdf' ? '📄' : '📝'}
                  </div>
                )}

                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-[#1a1917] truncate">{r.title || 'Untitled'}</p>
                  <TypeLabel type={type} />
                  {r.file_url && !isImage && (
                    <button
                      onClick={() => openViewer(viewerFilesForResource, 0)}
                      className="text-xs text-[#6b6762] hover:text-[#1a1917] underline underline-offset-2 mt-0.5 block text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-amber-500 rounded"
                    >
                      View
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </Collapsible>

      {viewerOpen && (
        <SourceViewer
          files={viewerFiles}
          initialIndex={viewerIndex}
          onClose={() => setViewerOpen(false)}
        />
      )}
    </>
  );
}
