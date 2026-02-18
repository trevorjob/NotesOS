/**
 * AI Chat Overlay Component
 * Full-page modal overlay for AI study assistant
 * Opens from floating button, covers entire screen with close button
 */

'use client';

import { X, MessageSquare } from 'lucide-react';
import { useState, useEffect } from 'react';
import { AIChat } from './AIChat';

interface AIChatOverlayProps {
    messages: any[];
    onSendMessage: (message: string) => Promise<void>;
    isLoading?: boolean;
    courseId: string;
}

export function AIChatOverlay({ messages, onSendMessage, isLoading, courseId }: AIChatOverlayProps) {
    const [isOpen, setIsOpen] = useState(false);

    // Prevent body scroll when overlay is open
    useEffect(() => {
        if (isOpen) {
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = '';
        }
        return () => {
            document.body.style.overflow = '';
        };
    }, [isOpen]);

    return (
        <>
            {/* Floating Action Button */}
            <button
                onClick={() => setIsOpen(true)}
                className="fixed bottom-6 right-6 w-14 h-14 bg-[var(--accent-primary)] hover:bg-[var(--accent-hover)] text-white rounded-full shadow-lg hover:shadow-xl transition-all duration-200 flex items-center justify-center z-40 group"
                aria-label="Open AI Chat"
            >
                <MessageSquare className="w-6 h-6 group-hover:scale-110 transition-transform" />
            </button>

            {/* Full-Page Overlay - always mounted for smooth transitions */}
            <div
                className={`fixed inset-0 z-50 flex items-center justify-center transition-all duration-300 ${isOpen
                        ? 'opacity-100 pointer-events-auto'
                        : 'opacity-0 pointer-events-none'
                    }`}
            >
                {/* Backdrop */}
                <div
                    className={`absolute inset-0 bg-black/50 backdrop-blur-sm transition-opacity duration-300 ${isOpen ? 'opacity-100' : 'opacity-0'
                        }`}
                    onClick={() => setIsOpen(false)}
                />

                {/* Modal Content */}
                <div className={`relative w-full h-full max-w-full max-h-full bg-[var(--bg-base)] shadow-2xl flex flex-col transition-all duration-300 ${isOpen ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-0'
                    }`}>
                    {/* Header */}
                    <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--glass-border)] glass-nav">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-full bg-[var(--accent-primary)]/10 flex items-center justify-center">
                                <MessageSquare className="w-5 h-5 text-[var(--accent-primary)]" />
                            </div>
                            <div>
                                <h2 className="text-lg font-semibold text-[var(--text-primary)]">
                                    AI Study Assistant
                                </h2>
                                <p className="text-xs text-[var(--text-tertiary)]">
                                    Ask questions about your course materials
                                </p>
                            </div>
                        </div>

                        {/* Close Button */}
                        <button
                            onClick={() => setIsOpen(false)}
                            className="w-10 h-10 rounded-lg hover:bg-[var(--bg-sunken)] flex items-center justify-center text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
                            aria-label="Close chat"
                        >
                            <X className="w-5 h-5" />
                        </button>
                    </div>

                    {/* Chat Container */}
                    <div className="flex-1 overflow-hidden">
                        <AIChat
                            messages={messages}
                            onSendMessage={onSendMessage}
                            isLoading={isLoading}
                        />
                    </div>
                </div>
            </div>
        </>
    );
}
