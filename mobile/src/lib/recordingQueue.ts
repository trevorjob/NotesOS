import { Directory, File, Paths } from 'expo-file-system';
import { PickedFile, uploadFilesToCloudinary } from '@/lib/cloudinary';
import { startCapture } from '@/lib/capture';

// Durable offline queue for in-app lecture recordings. A recording is fully local, so it
// can be captured with no network — we move the file into the persistent document
// directory and log it in a manifest. flushRecordingQueue() then feeds each one through
// the SAME path a picked audio file takes (Cloudinary upload → POST /capture), so the
// backend transcribe→organize→file pipeline is unchanged. Entries survive app restarts
// and only leave the queue once they've been accepted by the server.

const RECORDINGS_DIR = 'recordings';
const MANIFEST_NAME = 'queue.json';
// Drop an entry that keeps failing to upload for a non-network reason so one poison
// recording can't wedge the queue forever.
const MAX_UPLOAD_ATTEMPTS = 6;

export interface QueuedRecording {
  id: string;
  courseId: string;
  fileName: string;
  displayName: string;
  mimeType: string;
  createdAt: number;
  attempts: number;
}

function recordingsDir(): Directory {
  return new Directory(Paths.document, RECORDINGS_DIR);
}

function ensureDir(): Directory {
  const dir = recordingsDir();
  if (!dir.exists) dir.create();
  return dir;
}

function manifestFile(): File {
  return new File(recordingsDir(), MANIFEST_NAME);
}

function readManifest(): QueuedRecording[] {
  const file = manifestFile();
  if (!file.exists) return [];
  try {
    const parsed = JSON.parse(file.textSync());
    return Array.isArray(parsed) ? (parsed as QueuedRecording[]) : [];
  } catch {
    return []; // corrupt manifest — treat as empty rather than crash the capture screen
  }
}

function writeManifest(entries: QueuedRecording[]): void {
  ensureDir();
  manifestFile().write(JSON.stringify(entries));
}

/** Move a freshly-recorded file into durable storage and log it in the queue. */
export function enqueueRecording(courseId: string, source: PickedFile): QueuedRecording {
  const dir = ensureDir();
  const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  const ext = source.name.split('.').pop() || 'm4a';
  const fileName = `${id}.${ext}`;
  new File(source.uri).moveSync(new File(dir, fileName));

  const entry: QueuedRecording = {
    id,
    courseId,
    fileName,
    displayName: source.name,
    mimeType: source.mimeType,
    createdAt: Date.now(),
    attempts: 0,
  };
  writeManifest([...readManifest(), entry]);
  return entry;
}

export function pendingRecordingCount(): number {
  return readManifest().length;
}

function toPickedFile(entry: QueuedRecording): PickedFile {
  return { uri: new File(recordingsDir(), entry.fileName).uri, name: entry.displayName, mimeType: entry.mimeType };
}

function discard(entry: QueuedRecording): void {
  const file = new File(recordingsDir(), entry.fileName);
  if (file.exists) file.delete();
}

async function uploadOne(entry: QueuedRecording): Promise<void> {
  const uploaded = await uploadFilesToCloudinary([toPickedFile(entry)], `notesos/${entry.courseId}/capture`);
  await startCapture(entry.courseId, uploaded);
}

export interface FlushResult {
  uploaded: number;
  remaining: number;
}

/**
 * Try to upload every queued recording. Successes (and poison entries past the attempt
 * cap) leave the queue; entries that fail for a transient reason (offline) stay and are
 * retried next flush. Failures don't stop the loop, so one bad file can't block others.
 */
export async function flushRecordingQueue(): Promise<FlushResult> {
  const entries = readManifest();
  if (entries.length === 0) return { uploaded: 0, remaining: 0 };

  const remaining: QueuedRecording[] = [];
  let uploaded = 0;

  for (const entry of entries) {
    try {
      await uploadOne(entry);
      discard(entry);
      uploaded += 1;
    } catch {
      const attempts = entry.attempts + 1;
      if (attempts >= MAX_UPLOAD_ATTEMPTS) {
        discard(entry); // give up on a recording the server keeps rejecting
      } else {
        remaining.push({ ...entry, attempts });
      }
    }
  }

  writeManifest(remaining);
  return { uploaded, remaining: remaining.length };
}
