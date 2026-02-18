/**
 * NotesOS - Root Page
 * Redirects to /courses if authenticated, otherwise to /login.
 */

'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';

export default function HomePage() {
    const router = useRouter();
    const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

    useEffect(() => {
        if (isAuthenticated) {
            router.replace('/courses');
        } else {
            router.replace('/login');
        }
    }, [isAuthenticated, router]);

    return (
        <div className="min-h-screen bg-[var(--bg-base)] flex items-center justify-center">
            <div className="flex flex-col items-center gap-4">
                <div className="w-10 h-10 bg-[var(--accent-primary)] rounded-lg animate-pulse" />
                <p className="text-sm text-[var(--text-tertiary)]">Loading...</p>
            </div>
        </div>
    );
}
