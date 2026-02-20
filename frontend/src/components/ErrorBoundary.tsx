'use client';

import React from 'react';

interface ErrorBoundaryState {
    hasError: boolean;
}

export class ErrorBoundary extends React.Component<React.PropsWithChildren, ErrorBoundaryState> {
    state: ErrorBoundaryState = {
        hasError: false,
    };

    static getDerivedStateFromError(): ErrorBoundaryState {
        return { hasError: true };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
        console.error('[ErrorBoundary] Caught error:', error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return (
                <div className="min-h-screen bg-[var(--bg-base)] flex items-center justify-center px-4">
                    <div className="max-w-md w-full text-center">
                        <div className="w-12 h-12 mx-auto mb-4 rounded-xl bg-[var(--error)]/10 flex items-center justify-center">
                            <span className="text-[var(--error)] text-xl">!</span>
                        </div>
                        <h1 className="text-lg font-semibold text-[var(--text-primary)] mb-2">
                            Something went wrong
                        </h1>
                        <p className="text-sm text-[var(--text-secondary)] mb-4">
                            An unexpected error occurred. Try refreshing the page or going back to your courses.
                        </p>
                        <div className="flex justify-center gap-3">
                            <button
                                type="button"
                                onClick={() => window.location.reload()}
                                className="px-4 py-2 rounded-lg bg-[var(--accent-primary)] text-white text-sm font-medium hover:bg-[var(--accent-hover)] transition-colors"
                            >
                                Reload
                            </button>
                            <button
                                type="button"
                                onClick={() => (window.location.href = '/courses')}
                                className="px-4 py-2 rounded-lg bg-[var(--bg-sunken)] text-[var(--text-secondary)] text-sm font-medium hover:text-[var(--text-primary)] transition-colors"
                            >
                                Go to courses
                            </button>
                        </div>
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}

