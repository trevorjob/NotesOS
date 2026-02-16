/**
 * Markdown Renderer Component
 * Renders markdown content with GitHub-flavored markdown support
 * Styled to match the NotesOS design system
 */

'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ComponentPropsWithoutRef } from 'react';

interface MarkdownRendererProps {
    content: string;
    className?: string;
}

export function MarkdownRenderer({ content, className = '' }: MarkdownRendererProps) {
    return (
        <div className={`markdown-content ${className}`}>
            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                    // Headings
                    h1: ({ node, ...props }) => (
                        <h1 className="text-2xl font-semibold text-[var(--text-primary)] mb-3 mt-6 first:mt-0" {...props} />
                    ),
                    h2: ({ node, ...props }) => (
                        <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-2 mt-5 first:mt-0" {...props} />
                    ),
                    h3: ({ node, ...props }) => (
                        <h3 className="text-lg font-medium text-[var(--text-primary)] mb-2 mt-4 first:mt-0" {...props} />
                    ),
                    h4: ({ node, ...props }) => (
                        <h4 className="text-base font-medium text-[var(--text-primary)] mb-1.5 mt-3 first:mt-0" {...props} />
                    ),
                    h5: ({ node, ...props }) => (
                        <h5 className="text-sm font-medium text-[var(--text-primary)] mb-1 mt-2 first:mt-0" {...props} />
                    ),
                    h6: ({ node, ...props }) => (
                        <h6 className="text-sm font-medium text-[var(--text-secondary)] mb-1 mt-2 first:mt-0" {...props} />
                    ),

                    // Paragraphs and text
                    p: ({ node, ...props }) => (
                        <p className="text-[var(--text-secondary)] mb-3 leading-relaxed" {...props} />
                    ),
                    strong: ({ node, ...props }) => (
                        <strong className="font-semibold text-[var(--text-primary)]" {...props} />
                    ),
                    em: ({ node, ...props }) => (
                        <em className="italic text-[var(--text-secondary)]" {...props} />
                    ),

                    // Lists
                    ul: ({ node, ...props }) => (
                        <ul className="list-disc list-inside mb-3 space-y-1 text-[var(--text-secondary)]" {...props} />
                    ),
                    ol: ({ node, ...props }) => (
                        <ol className="list-decimal list-inside mb-3 space-y-1 text-[var(--text-secondary)]" {...props} />
                    ),
                    li: ({ node, ...props }) => (
                        <li className="text-[var(--text-secondary)]" {...props} />
                    ),

                    // Links
                    a: ({ node, ...props }) => (
                        <a
                            className="text-[var(--accent-primary)] hover:underline"
                            target={props.href?.startsWith('http') ? '_blank' : undefined}
                            rel={props.href?.startsWith('http') ? 'noopener noreferrer' : undefined}
                            {...props}
                        />
                    ),

                    // Code
                    code: ({ node, inline, ...props }: any) =>
                        inline ? (
                            <code
                                className="px-1.5 py-0.5 rounded bg-[var(--bg-sunken)] text-[var(--accent-primary)] text-sm font-mono"
                                {...props}
                            />
                        ) : (
                            <code
                                className="block px-4 py-3 rounded-lg bg-[var(--bg-sunken)] text-[var(--text-primary)] text-sm font-mono overflow-x-auto mb-3"
                                {...props}
                            />
                        ),
                    pre: ({ node, ...props }) => (
                        <pre className="mb-3" {...props} />
                    ),

                    // Blockquotes
                    blockquote: ({ node, ...props }) => (
                        <blockquote
                            className="border-l-4 border-[var(--accent-primary)] pl-4 py-2 mb-3 text-[var(--text-secondary)] italic bg-[var(--bg-sunken)]/30"
                            {...props}
                        />
                    ),

                    // Horizontal rule
                    hr: ({ node, ...props }) => (
                        <hr className="border-t border-[var(--glass-border)] my-4" {...props} />
                    ),

                    // Tables
                    table: ({ node, ...props }) => (
                        <div className="overflow-x-auto mb-3">
                            <table className="min-w-full border border-[var(--glass-border)] rounded-lg" {...props} />
                        </div>
                    ),
                    thead: ({ node, ...props }) => (
                        <thead className="bg-[var(--bg-sunken)]" {...props} />
                    ),
                    tbody: ({ node, ...props }) => (
                        <tbody {...props} />
                    ),
                    tr: ({ node, ...props }) => (
                        <tr className="border-b border-[var(--glass-border)] last:border-0" {...props} />
                    ),
                    th: ({ node, ...props }) => (
                        <th className="px-4 py-2 text-left text-sm font-medium text-[var(--text-primary)]" {...props} />
                    ),
                    td: ({ node, ...props }) => (
                        <td className="px-4 py-2 text-sm text-[var(--text-secondary)]" {...props} />
                    ),

                    // Images
                    img: ({ node, ...props }) => (
                        <img
                            className="rounded-lg max-w-full h-auto mb-3"
                            {...props}
                        />
                    ),
                }}
            >
                {content}
            </ReactMarkdown>
        </div>
    );
}
