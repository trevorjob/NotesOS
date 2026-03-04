/**
 * NotesOS - Direct Cloudinary Upload Helper
 *
 * Uploads files directly from the browser to Cloudinary (unsigned).
 * Files are uploaded concurrently; order is preserved via their original index.
 *
 * Usage:
 *   const results = await uploadFilesToCloudinary(files, folder, onProgress);
 *   // results[i] corresponds to files[i], order guaranteed.
 */

const CLOUD_NAME = process.env.NEXT_PUBLIC_CLOUDINARY_CLOUD_NAME!;
const UPLOAD_PRESET = process.env.NEXT_PUBLIC_CLOUDINARY_UPLOAD_PRESET!;
const UPLOAD_URL = `https://api.cloudinary.com/v1_1/${CLOUD_NAME}/auto/upload`;

export interface CloudinaryUploadResult {
    url: string;
    public_id: string;
    filename: string;
    file_order: number; // original index in the uploaded files array
}

/**
 * Upload one file to Cloudinary with progress tracking.
 * Returns the secure URL and public_id on success.
 */
function uploadSingleFile(
    file: File,
    folder: string,
    index: number,
    onProgress?: (loaded: number, total: number, index: number) => void
): Promise<CloudinaryUploadResult> {
    return new Promise((resolve, reject) => {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('upload_preset', UPLOAD_PRESET);
        formData.append('folder', folder);

        const xhr = new XMLHttpRequest();

        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable && onProgress) {
                onProgress(e.loaded, e.total, index);
            }
        });

        xhr.addEventListener('load', () => {
            if (xhr.status === 200) {
                const result = JSON.parse(xhr.responseText);
                resolve({
                    url: result.secure_url,
                    public_id: result.public_id,
                    filename: file.name,
                    file_order: index,
                });
            } else {
                let message = `Cloudinary upload failed (${xhr.status})`;
                try {
                    const err = JSON.parse(xhr.responseText);
                    message = err?.error?.message ?? message;
                } catch { }
                reject(new Error(message));
            }
        });

        xhr.addEventListener('error', () => reject(new Error('Network error during upload')));
        xhr.addEventListener('abort', () => reject(new Error('Upload aborted')));

        xhr.open('POST', UPLOAD_URL);
        xhr.send(formData);
    });
}

/**
 * Upload all files concurrently to Cloudinary.
 * Results are returned in the same order as the input files array.
 *
 * @param files     - Array of File objects (order matters — used as file_order)
 * @param folder    - Cloudinary folder path (e.g. "notesos/{course_id}/{topic_id}")
 * @param onProgress - Optional overall progress callback (0-100)
 */
export async function uploadFilesToCloudinary(
    files: File[],
    folder: string,
    onProgress?: (percent: number) => void
): Promise<CloudinaryUploadResult[]> {
    if (!CLOUD_NAME || !UPLOAD_PRESET) {
        throw new Error(
            'Cloudinary is not configured. Set NEXT_PUBLIC_CLOUDINARY_CLOUD_NAME and NEXT_PUBLIC_CLOUDINARY_UPLOAD_PRESET.'
        );
    }

    // Track bytes loaded per file index for accurate aggregate progress
    const loadedPerFile = new Array(files.length).fill(0);
    const totalBytes = files.reduce((sum, f) => sum + f.size, 0);

    const handleProgress = (loaded: number, _total: number, index: number) => {
        loadedPerFile[index] = loaded;
        if (onProgress && totalBytes > 0) {
            const totalLoaded = loadedPerFile.reduce((a, b) => a + b, 0);
            onProgress(Math.round((totalLoaded / totalBytes) * 100));
        }
    };

    // Upload all files concurrently — order preserved by Promise.all
    const results = await Promise.all(
        files.map((file, index) =>
            uploadSingleFile(file, folder, index, onProgress ? handleProgress : undefined)
        )
    );

    // Sort by file_order just to be safe (Promise.all preserves order, but be explicit)
    return results.sort((a, b) => a.file_order - b.file_order);
}
