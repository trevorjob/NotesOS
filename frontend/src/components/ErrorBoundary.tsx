'use client';

import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    try {
      // Report to PostHog if available
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const posthog = require('posthog-js').default;
      posthog.captureException(error, { extra: { componentStack: info.componentStack } });
    } catch {
      // PostHog not loaded — silent
    }
    console.error('[ErrorBoundary]', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="min-h-screen flex items-center justify-center bg-[#F5F3EE] px-4">
          <div className="max-w-md text-center space-y-4">
            <p className="text-2xl font-semibold text-[#1a1917]">Something went wrong</p>
            <p className="text-sm text-[#6b6762]">
              An unexpected error occurred. Try refreshing the page.
            </p>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 rounded-xl bg-[#1a1917] text-white text-sm hover:opacity-90 transition-opacity"
            >
              Refresh
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
