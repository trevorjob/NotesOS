import * as DocumentPicker from 'expo-document-picker';
import * as ImagePicker from 'expo-image-picker';
import { PickedFile } from '@/lib/cloudinary';

// Thin wrappers over the Expo pickers that normalise everything to PickedFile
// ({ uri, name, mimeType }) so the capture screen doesn't care which source a file
// came from. A cancelled picker returns [] (not an error) — the caller just stops.

// Raised when a permission the user must grant is denied, so the screen can show a
// clear "enable it in Settings" message rather than a generic failure.
export class PermissionDeniedError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'PermissionDeniedError';
  }
}

function nameFromUri(uri: string, fallbackExt: string): string {
  const tail = uri.split('/').pop();
  if (tail && tail.includes('.')) return tail;
  return `capture-${Date.now()}.${fallbackExt}`;
}

function imageAssetToPicked(asset: ImagePicker.ImagePickerAsset): PickedFile {
  const mimeType = asset.mimeType ?? 'image/jpeg';
  const ext = mimeType.split('/')[1] ?? 'jpg';
  return {
    uri: asset.uri,
    name: asset.fileName ?? nameFromUri(asset.uri, ext),
    mimeType,
  };
}

/** Files from the OS file browser — PDF/DOCX/images/audio, multiple at once. */
export async function pickDocuments(): Promise<PickedFile[]> {
  const result = await DocumentPicker.getDocumentAsync({
    multiple: true,
    copyToCacheDirectory: true,
  });
  if (result.canceled) return [];
  return result.assets.map((asset) => ({
    uri: asset.uri,
    name: asset.name ?? nameFromUri(asset.uri, 'bin'),
    mimeType: asset.mimeType ?? 'application/octet-stream',
  }));
}

/**
 * Snap one or more photos — boards, slides, handwriting. The camera is single-shot per
 * launch, so this bursts: after each photo it re-opens the camera, accumulating shots
 * until the user cancels (done). Cancelling the very first launch returns [].
 */
export async function takePhoto(): Promise<PickedFile[]> {
  const permission = await ImagePicker.requestCameraPermissionsAsync();
  if (!permission.granted) {
    throw new PermissionDeniedError('Camera access is off. Enable it in Settings to snap a photo.');
  }
  const photos: PickedFile[] = [];
  // Keep re-opening the camera until the user backs out — that's how they signal "done".
  for (;;) {
    const result = await ImagePicker.launchCameraAsync({ quality: 0.8, mediaTypes: ['images'] });
    if (result.canceled) break;
    photos.push(...result.assets.map(imageAssetToPicked));
  }
  return photos;
}

/** Multiple photos from the library — grouped together on capture. */
export async function pickPhotos(): Promise<PickedFile[]> {
  const permission = await ImagePicker.requestMediaLibraryPermissionsAsync();
  if (!permission.granted) {
    throw new PermissionDeniedError('Photo access is off. Enable it in Settings to choose photos.');
  }
  const result = await ImagePicker.launchImageLibraryAsync({
    allowsMultipleSelection: true,
    quality: 0.8,
    mediaTypes: ['images'],
  });
  if (result.canceled) return [];
  return result.assets.map(imageAssetToPicked);
}
