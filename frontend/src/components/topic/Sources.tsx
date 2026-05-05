import { Collapsible } from '@/components/ui/Collapsible';

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
  if (resources.length === 0) return null;

  return (
    <Collapsible title="Sources" count={resources.length} storageKey="sources-section">
      <div className="space-y-3">
        {resources.map((r) => {
          const type = r.resource_type?.toLowerCase();
          const isImage = type === 'image' || type === 'handwritten';
          const imageFiles = r.files && r.files.length > 0 ? r.files : null;

          return (
            <div key={r.id} className="flex items-start gap-3">
              {/* Image thumbnails — iterate files[] array */}
              {isImage && imageFiles ? (
                <div className="flex gap-1.5 shrink-0 flex-wrap">
                  {imageFiles.slice(0, 3).map((f) => (
                    <a key={f.id} href={f.file_url} target="_blank" rel="noopener noreferrer">
                      <img
                        src={f.file_url}
                        alt={r.title || 'Resource'}
                        className="h-16 w-16 rounded-lg object-cover border border-[#dedad4] hover:opacity-90 transition-opacity"
                      />
                    </a>
                  ))}
                  {imageFiles.length > 3 && (
                    <div className="h-16 w-16 rounded-lg bg-[#f0eeea] border border-[#dedad4] flex items-center justify-center text-xs text-[#6b6762]">
                      +{imageFiles.length - 3}
                    </div>
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
                  <a
                    href={r.file_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-[#6b6762] hover:text-[#1a1917] underline underline-offset-2 mt-0.5 block"
                  >
                    View
                  </a>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </Collapsible>
  );
}
