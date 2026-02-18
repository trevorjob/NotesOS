/**
 * AI Chat Component
 * Chat panel for study questions with sources and conversation history
 */

'use client';

import { useState, useRef, useEffect } from 'react';
import { Send, Loader2, ExternalLink } from 'lucide-react';
import { Button } from './ui';
import { MarkdownRenderer } from './MarkdownRenderer';

interface Message {
    role: 'user' | 'assistant';
    content: string;
    sources?: Array<{
        title: string;
        url?: string;
        resource_id?: string;
    }>;
    created_at: string;
}

interface AIChatProps {
    messages: Message[];
    onSendMessage: (message: string) => Promise<void>;
    isLoading?: boolean;
}

export function AIChat({ messages, onSendMessage, isLoading = false }: AIChatProps) {
    const [input, setInput] = useState('');
    const [isSending, setIsSending] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!input.trim() || isSending) return;

        const message = input.trim();
        setInput('');
        setIsSending(true);

        try {
            await onSendMessage(message);
        } catch (error) {
            console.error('Failed to send message:', error);
        } finally {
            setIsSending(false);
        }
    };

    return (
        <div className="flex flex-col h-full">
            {/* Messages */}
            <div className="flex-1 overflow-y-auto space-y-4 p-4 min-h-0">
                {messages.length === 0 ? (
                    <div className="flex items-center justify-center h-full text-center">
                        <div>
                            <p className="text-sm text-[var(--text-tertiary)] mb-2">
                                No messages yet
                            </p>
                            <p className="text-xs text-[var(--text-tertiary)]">
                                Ask a question to start studying
                            </p>
                        </div>
                    </div>
                ) : (
                    messages.map((message, index) => (
                        <div
                            key={index}
                            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                        >
                            <div
                                className={`max-w-[80%] rounded-lg px-4 py-2 ${message.role === 'user'
                                    ? 'bg-[var(--accent-primary)] text-white'
                                    : 'bg-[var(--bg-sunken)] text-[var(--text-primary)]'
                                    }`}
                            >
                                <div className="text-sm">
                                    <MarkdownRenderer content={message.content} />
                                </div>

                                {/* Sources */}
                                {message.sources && message.sources.length > 0 && (
                                    <div className="mt-2 pt-2 border-t border-[var(--glass-border)] space-y-1">
                                        <p className="text-xs opacity-70">Sources:</p>
                                        {message.sources.map((source, idx) => (
                                            <div
                                                key={idx}
                                                className="flex items-center gap-1 text-xs opacity-80"
                                            >
                                                <ExternalLink className="w-3 h-3" />
                                                {source.url ? (
                                                    <a
                                                        href={source.url}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="hover:underline"
                                                    >
                                                        {source.title}
                                                    </a>
                                                ) : (
                                                    <span>{source.title}</span>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    ))
                )}

                {/* Loading indicator */}
                {(isLoading || isSending) && (
                    <div className="flex justify-start">
                        <div className="flex items-center gap-2 px-4 py-2 bg-[var(--bg-sunken)] rounded-lg">
                            <Loader2 className="w-4 h-4 animate-spin text-[var(--text-tertiary)]" />
                            <span className="text-sm text-[var(--text-secondary)]">Thinking...</span>
                        </div>
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input */}
            <form onSubmit={handleSubmit} className="p-4 border-t border-[var(--glass-border)]">
                <div className="flex gap-2">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="Ask a question..."
                        disabled={isSending}
                        className="flex-1 px-4 py-2 bg-[var(--bg-sunken)] border border-[var(--glass-border)] rounded-lg text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-primary)] disabled:opacity-50"
                    />
                    <Button
                        type="submit"
                        variant="primary"
                        size="md"
                        disabled={!input.trim() || isSending}
                        className="px-4"
                    >
                        <Send className="w-4 h-4" />
                    </Button>
                </div>
            </form>
        </div>
    );
}
