/**
 * File Upload Component
 * Drag & drop file upload with progress indicator
 */

'use client';

import { useState, useRef, DragEvent } from 'react';
import { Upload, X, File } from 'lucide-react';
import { Button } from './ui';

interface FileUploadProps {
    onUpload: (files: File[], title?: string, isHandwritten?: boolean) => Promise<void>;
    isUploading?: boolean;
    uploadProgress?: number;
}

export function FileUpload({ onUpload, isUploading = false, uploadProgress = 0 }: FileUploadProps) {
    const [isDragging, setIsDragging] = useState(false);
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
    const [title, setTitle] = useState('');
    const [isHandwritten, setIsHandwritten] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setIsDragging(false);
    };

    const handleDrop = (e: DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        setIsDragging(false);

        const files = Array.from(e.dataTransfer.files).filter(file =>
            file.type.startsWith('image/') ||
            file.type === 'application/pdf' ||
            file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        );

        setSelectedFiles(prev => [...prev, ...files]);
    };

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files) {
            const files = Array.from(e.target.files);
            setSelectedFiles(prev => [...prev, ...files]);
        }
    };

    const removeFile = (index: number) => {
        setSelectedFiles(prev => prev.filter((_, i) => i !== index));
    };

    const handleUpload = async () => {
        if (selectedFiles.length === 0) return;

        try {
            await onUpload(selectedFiles, title || undefined, isHandwritten);
            // Reset on success
            setSelectedFiles([]);
            setTitle('');
            setIsHandwritten(false);
        } catch (error) {
            console.error('Upload failed:', error);
        }
    };

    return (
        <div className="space-y-3">
            {/* Drop zone */}
            <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`
          relative border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer
          ${isDragging
                        ? 'border-[var(--accent-primary)] bg-[var(--accent-primary)]/5'
                        : 'border-[var(--glass-border)] hover:border-[var(--text-tertiary)]'
                    }
        `}
                onClick={() => fileInputRef.current?.click()}
            >
                <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept="image/*,.pdf,.docx"
                    onChange={handleFileSelect}
                    className="hidden"
                />

                <Upload className="w-8 h-8 mx-auto mb-2 text-[var(--text-tertiary)]" />
                <p className="text-sm text-[var(--text-secondary)] mb-1">
                    Drop files here or click to browse
                </p>
                <p className="text-xs text-[var(--text-tertiary)]">
                    Supports images, PDF, DOCX
                </p>
            </div>

            {/* Selected files */}
            {selectedFiles.length > 0 && (
                <div className="space-y-2">
                    <div className="space-y-1">
                        {selectedFiles.map((file, index) => (
                            <div
                                key={index}
                                className="flex items-center gap-2 px-3 py-2 bg-[var(--bg-sunken)] rounded text-sm"
                            >
                                <File className="w-4 h-4 text-[var(--text-tertiary)] flex-shrink-0" />
                                <span className="flex-1 truncate text-[var(--text-secondary)]">
                                    {file.name}
                                </span>
                                <span className="text-xs text-[var(--text-tertiary)] flex-shrink-0">
                                    {(file.size / 1024 / 1024).toFixed(1)} MB
                                </span>
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        removeFile(index);
                                    }}
                                    className="p-1 hover:bg-[var(--bg-base)] rounded text-[var(--text-tertiary)] hover:text-[var(--error)]"
                                >
                                    <X className="w-4 h-4" />
                                </button>
                            </div>
                        ))}
                    </div>

                    {/* Options */}
                    <div className="space-y-2">
                        <input
                            type="text"
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            placeholder="Title (optional)"
                            className="w-full px-3 py-2 bg-[var(--bg-sunken)] border border-[var(--glass-border)] rounded text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)]"
                        />

                        <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
                            <input
                                type="checkbox"
                                checked={isHandwritten}
                                onChange={(e) => setIsHandwritten(e.target.checked)}
                                className="rounded border-[var(--glass-border)] text-[var(--accent-primary)] focus:ring-2 focus:ring-[var(--accent-primary)]"
                            />
                            Handwritten notes (better OCR)
                        </label>
                    </div>

                    {/* Upload button */}
                    <Button
                        onClick={handleUpload}
                        variant="primary"
                        disabled={isUploading}
                        className="w-full"
                    >
                        {isUploading ? `Uploading... ${uploadProgress}%` : `Upload ${selectedFiles.length} file${selectedFiles.length > 1 ? 's' : ''}`}
                    </Button>

                    {/* Progress bar */}
                    {isUploading && (
                        <div className="h-1 bg-[var(--bg-sunken)] rounded-full overflow-hidden">
                            <div
                                className="h-full bg-[var(--accent-primary)] transition-all duration-300"
                                style={{ width: `${uploadProgress}%` }}
                            />
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
