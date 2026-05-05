'use client';

import { useEffect, useRef, useState, useCallback } from 'react';

export interface ViewerFile {
    id: string;
    url: string;
    type: 'image' | 'pdf';
    label: string; // resource title + page indicator
}

interface SourceViewerProps {
    files: ViewerFile[];
    initialIndex?: number;
    onClose: () => void;
}

export function SourceViewer({ files, initialIndex = 0, onClose }: SourceViewerProps) {
    const [index, setIndex] = useState(initialIndex);
    const [zoomed, setZoomed] = useState(false);
    const touchStartX = useRef<number | null>(null);
    const touchStartY = useRef<number | null>(null);
    const overlayRef = useRef<HTMLDivElement>(null);

    const current = files[index];
    const hasPrev = index > 0;
    const hasNext = index < files.length - 1;

    const prev = useCallback(() => { if (hasPrev) setIndex((i) => i - 1); setZoomed(false); }, [hasPrev]);
    const next = useCallback(() => { if (hasNext) setIndex((i) => i + 1); setZoomed(false); }, [hasNext]);

    // Keyboard navigation
    useEffect(() => {
        function onKey(e: KeyboardEvent) {
            if (e.key === 'Escape') onClose();
            if (e.key === 'ArrowLeft') prev();
            if (e.key === 'ArrowRight') next();
        }
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [prev, next, onClose]);

    // Prevent body scroll while open
    useEffect(() => {
        const prev = document.body.style.overflow;
        document.body.style.overflow = 'hidden';
        return () => { document.body.style.overflow = prev; };
    }, []);

    // Touch swipe
    function onTouchStart(e: React.TouchEvent) {
        touchStartX.current = e.touches[0].clientX;
        touchStartY.current = e.touches[0].clientY;
    }

    function onTouchEnd(e: React.TouchEvent) {
        if (touchStartX.current === null || touchStartY.current === null) return;
        const dx = e.changedTouches[0].clientX - touchStartX.current;
        const dy = e.changedTouches[0].clientY - touchStartY.current;
        touchStartX.current = null;
        touchStartY.current = null;

        // Only treat as horizontal swipe if dx > dy (not a scroll)
        if (Math.abs(dx) < 40 || Math.abs(dx) < Math.abs(dy)) return;
        if (dx < 0) next();
        else prev();
    }

    return (
        <div
            ref={overlayRef}
            className="fixed inset-0 z-50 bg-black/90 flex flex-col"
            onTouchStart={onTouchStart}
            onTouchEnd={onTouchEnd}
        >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 flex-shrink-0">
                <span className="text-white/70 text-sm truncate max-w-[60%]">{current?.label}</span>
                <div className="flex items-center gap-4">
                    {files.length > 1 && (
                        <span className="text-white/50 text-xs">{index + 1} / {files.length}</span>
                    )}
                    <button
                        onClick={onClose}
                        className="text-white/70 hover:text-white transition-colors p-1"
                        aria-label="Close viewer"
                    >
                        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                            <path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                        </svg>
                    </button>
                </div>
            </div>

            {/* Content */}
            <div className="flex-1 flex items-center justify-center relative overflow-hidden min-h-0">
                {/* Prev button */}
                {hasPrev && (
                    <button
                        onClick={prev}
                        className="absolute left-2 z-10 p-2 rounded-full bg-black/40 hover:bg-black/60 text-white transition-colors"
                        aria-label="Previous"
                    >
                        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                            <path d="M12 4l-8 6 8 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                    </button>
                )}

                {/* Next button */}
                {hasNext && (
                    <button
                        onClick={next}
                        className="absolute right-2 z-10 p-2 rounded-full bg-black/40 hover:bg-black/60 text-white transition-colors"
                        aria-label="Next"
                    >
                        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                            <path d="M8 4l8 6-8 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                    </button>
                )}

                {/* Image */}
                {current?.type === 'image' && (
                    <img
                        key={current.id}
                        src={current.url}
                        alt={current.label}
                        onClick={() => setZoomed((z) => !z)}
                        className="max-h-full max-w-full object-contain select-none transition-transform duration-200 cursor-zoom-in"
                        style={{
                            transform: zoomed ? 'scale(2)' : 'scale(1)',
                            transformOrigin: 'center center',
                            touchAction: 'pinch-zoom',
                            cursor: zoomed ? 'zoom-out' : 'zoom-in',
                        }}
                        draggable={false}
                    />
                )}

                {/* PDF */}
                {current?.type === 'pdf' && (
                    <iframe
                        key={current.id}
                        src={current.url}
                        className="w-full h-full border-0"
                        title={current.label}
                    />
                )}
            </div>

            {/* Dot strip for multi-file resources */}
            {files.length > 1 && (
                <div className="flex justify-center gap-1.5 py-3 flex-shrink-0">
                    {files.map((_, i) => (
                        <button
                            key={i}
                            onClick={() => { setIndex(i); setZoomed(false); }}
                            className={`h-1.5 rounded-full transition-all ${
                                i === index ? 'w-4 bg-white' : 'w-1.5 bg-white/30'
                            }`}
                            aria-label={`Go to ${i + 1}`}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}
