import { api } from '@/lib/api';
import { CloudinaryUploadResult } from '@/lib/cloudinary';

// Capture client — kicks off a bulk dump. The endpoint takes files already on
// Cloudinary and returns 202 immediately; the actual transcribe→organize→file work
// happens in a worker that reports progress over the course WebSocket (see
// courseSocket.ts + the CaptureEvent union below, which mirror the worker's payloads).

export interface CaptureAccepted {
  batch_id: string;
  status: string;
  file_count: number;
}

/** POST the uploaded files' URLs to start a capture batch. */
export async function startCapture(
  courseId: string,
  files: CloudinaryUploadResult[],
  title?: string
): Promise<CaptureAccepted> {
  const { data } = await api.post(`/api/courses/${courseId}/capture`, {
    files: files.map((f) => ({ url: f.url, filename: f.filename, file_order: f.file_order })),
    title,
  });
  return data;
}

// ── Outline scaffold (the syllabus → topic-skeleton surface) ─────────────────────
// Distinct from the dump: POST /api/courses/{id}/outline is synchronous (no worker /
// WebSocket). Paste the syllabus text and/or snap photos of it (Cloudinary URLs, vision-
// transcribed server-side); the LLM parses it into empty labeled topics, deduped by title.

export interface OutlineTopic {
  id: string;
  title: string;
  description: string | null;
  week_number: number | null;
  order_index: number;
}

export interface OutlineResult {
  created: OutlineTopic[];
  skipped: string[]; // titles that already existed (case-insensitive) — no dupes
}

export async function scaffoldOutline(
  courseId: string,
  params: { text?: string; imageUrls?: string[] }
): Promise<OutlineResult> {
  const { data } = await api.post(`/api/courses/${courseId}/outline`, {
    text: params.text,
    image_urls: params.imageUrls ?? [],
  });
  return data;
}

// ── Capture WebSocket events (must match app/workers/capture_worker.py) ──────────

export interface CaptureFailedItem {
  url: string | null;
  filename: string | null;
  error: string;
}

export interface CaptureTopicResult {
  topic_id: string;
  title?: string;
  resources: { resource_id: string; title: string; needs_review: boolean }[];
}

export type CaptureEvent =
  | { type: 'capture_progress'; batch_id: string; stage: 'transcribing' | 'organizing'; file_count: number }
  | { type: 'capture_complete'; batch_id: string; topics: CaptureTopicResult[]; failed: CaptureFailedItem[] }
  | { type: 'capture_failed'; batch_id: string; failed: CaptureFailedItem[] };

export function isCaptureEvent(msg: { type?: string }): msg is CaptureEvent {
  return (
    msg.type === 'capture_progress' ||
    msg.type === 'capture_complete' ||
    msg.type === 'capture_failed'
  );
}
