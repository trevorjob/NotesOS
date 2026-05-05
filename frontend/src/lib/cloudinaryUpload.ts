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

const IMAGE_COMPRESS_THRESHOLD = 500 * 1024; // 500 KB
const IMAGE_MAX_DIMENSION = 2000;
const IMAGE_QUALITY = 0.80;

/**
 * Compress an image File to WebP if it exceeds the size threshold.
 * Returns the original file unchanged for PDFs, DOCX, or images already under the threshold.
 */
async function maybeCompressImage(file: File): Promise<File> {
    if (!file.type.startsWith('image/')) return file;
    if (file.size <= IMAGE_COMPRESS_THRESHOLD) return file;

    return new Promise((resolve) => {
        const img = new Image();
        const objectUrl = URL.createObjectURL(file);

        img.onload = () => {
            URL.revokeObjectURL(objectUrl);

            let { width, height } = img;
            if (width > IMAGE_MAX_DIMENSION || height > IMAGE_MAX_DIMENSION) {
                const ratio = Math.min(IMAGE_MAX_DIMENSION / width, IMAGE_MAX_DIMENSION / height);
                width = Math.round(width * ratio);
                height = Math.round(height * ratio);
            }

            const canvas = document.createElement('canvas');
            canvas.width = width;
            canvas.height = height;
            const ctx = canvas.getContext('2d');
            if (!ctx) { resolve(file); return; }
            ctx.drawImage(img, 0, 0, width, height);

            canvas.toBlob(
                (blob) => {
                    if (!blob || blob.size >= file.size) {
                        resolve(file); // compression made it bigger — keep original
                        return;
                    }
                    const compressed = new File(
                        [blob],
                        file.name.replace(/\.[^.]+$/, '.webp'),
                        { type: 'image/webp', lastModified: file.lastModified }
                    );
                    resolve(compressed);
                },
                'image/webp',
                IMAGE_QUALITY
            );
        };

        img.onerror = () => { URL.revokeObjectURL(objectUrl); resolve(file); };
        img.src = objectUrl;
    });
}

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

    // Compress images above the threshold before uploading
    const processedFiles = await Promise.all(files.map(maybeCompressImage));

    // Track bytes loaded per file index for accurate aggregate progress
    const loadedPerFile = new Array(processedFiles.length).fill(0);
    const totalBytes = processedFiles.reduce((sum, f) => sum + f.size, 0);

    const handleProgress = (loaded: number, _total: number, index: number) => {
        loadedPerFile[index] = loaded;
        if (onProgress && totalBytes > 0) {
            const totalLoaded = loadedPerFile.reduce((a, b) => a + b, 0);
            onProgress(Math.round((totalLoaded / totalBytes) * 100));
        }
    };

    // Upload all files concurrently — order preserved by Promise.all
    const results = await Promise.all(
        processedFiles.map((file, index) =>
            uploadSingleFile(file, folder, index, onProgress ? handleProgress : undefined)
        )
    );

    // Sort by file_order just to be safe (Promise.all preserves order, but be explicit)
    return results.sort((a, b) => a.file_order - b.file_order);
}
