/**
 * NotesOS - Auth Redirect
 * For (auth) routes: redirects to /courses if already authenticated.
 */

'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';

interface AuthRedirectProps {
    children: React.ReactNode;
}

export function AuthRedirect({ children }: AuthRedirectProps) {
    const router = useRouter();
    const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

    useEffect(() => {
        if (isAuthenticated) {
            router.replace('/courses');
        }
    }, [isAuthenticated, router]);

    if (isAuthenticated) {
        return (
            <div className="min-h-screen bg-[var(--bg-base)] flex items-center justify-center">
                <div className="flex flex-col items-center gap-4">
                    <div className="w-10 h-10 bg-[var(--accent-primary)] rounded-lg animate-pulse" />
                    <p className="text-sm text-[var(--text-tertiary)]">Redirecting...</p>
                </div>
            </div>
        );
    }

    return <>{children}</>;
}
