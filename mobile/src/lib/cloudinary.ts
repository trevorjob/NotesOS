// Direct Cloudinary upload from the device — mirrors the web's unsigned-preset flow
// (frontend/src/lib/cloudinaryUpload.ts). Capture's endpoint only accepts URLs of files
// already on Cloudinary, so the device uploads first, then POSTs the URLs. The cloud name
// and unsigned preset are public by design (safe to ship in EXPO_PUBLIC_* vars).
//
// SDK 57 note: the global `fetch`/`FormData` are Expo's "winter" implementations, whose
// multipart encoder only accepts string or Blob/File parts. The old React-Native
// `{ uri, name, type }` file-object convention is NOT supported and throws "Unsupported
// FormData implementation". We therefore wrap the local file URI in an expo-file-system
// `File` (implements the Blob interface) and append that instead.

import { File } from 'expo-file-system';

const CLOUD_NAME = process.env.EXPO_PUBLIC_CLOUDINARY_CLOUD_NAME ?? '';
const UPLOAD_PRESET = process.env.EXPO_PUBLIC_CLOUDINARY_UPLOAD_PRESET ?? '';
const UPLOAD_URL = `https://api.cloudinary.com/v1_1/${CLOUD_NAME}/auto/upload`;

// A file chosen on-device: RN's FormData wants { uri, name, type } for multipart upload.
export interface PickedFile {
  uri: string;
  name: string;
  mimeType: string;
}

export interface CloudinaryUploadResult {
  url: string;
  public_id: string;
  filename: string;
  file_order: number;
}

export function isCloudinaryConfigured(): boolean {
  return !!CLOUD_NAME && !!UPLOAD_PRESET;
}

async function uploadSingleFile(file: PickedFile, folder: string, index: number): Promise<CloudinaryUploadResult> {
  const form = new FormData();
  // SDK 57: append a File (Blob-compatible), not the legacy { uri, name, type } object —
  // Expo's winter FormData encoder rejects the latter. File.name carries the filename part.
  form.append('file', new File(file.uri));
  form.append('upload_preset', UPLOAD_PRESET);
  form.append('folder', folder);

  const res = await fetch(UPLOAD_URL, { method: 'POST', body: form });
  if (!res.ok) {
    let message = `Cloudinary upload failed (${res.status})`;
    try {
      const body = await res.json();
      message = body?.error?.message ?? message;
    } catch {
      // non-JSON error body — keep the status message
    }
    throw new Error(message);
  }

  const data = await res.json();
  return { url: data.secure_url, public_id: data.public_id, filename: file.name, file_order: index };
}

/**
 * Upload all picked files to Cloudinary concurrently. Results come back in the same
 * order as the input (file_order = original index), which capture uses to preserve
 * multi-page ordering.
 */
export async function uploadFilesToCloudinary(files: PickedFile[], folder: string): Promise<CloudinaryUploadResult[]> {
  if (!isCloudinaryConfigured()) {
    throw new Error(
      'Cloudinary isn’t configured. Set EXPO_PUBLIC_CLOUDINARY_CLOUD_NAME and EXPO_PUBLIC_CLOUDINARY_UPLOAD_PRESET.'
    );
  }
  const results = await Promise.all(files.map((file, index) => uploadSingleFile(file, folder, index)));
  return results.sort((a, b) => a.file_order - b.file_order);
}
