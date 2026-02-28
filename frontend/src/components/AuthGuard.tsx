/**
 * NotesOS - Auth Guard
 * Protects (main) routes: validates session and redirects to /login if not authenticated.
 */

'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import { api } from '@/lib/api';

interface AuthGuardProps {
    children: React.ReactNode;
}

export function AuthGuard({ children }: AuthGuardProps) {
    const router = useRouter();
    const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
    const clearSession = useAuthStore((state) => state.clearSession);
    const setUser = useAuthStore((state) => state.setUser);
    const [isValidating, setIsValidating] = useState(true);
    const isValidatingRef = useRef(false);

    useEffect(() => {
        if (!isAuthenticated) {
            router.replace('/login');
            setIsValidating(false);
            return;
        }

        if (isValidatingRef.current) return;
        isValidatingRef.current = true;

        let cancelled = false;

        const validateSession = async () => {
            try {
                const response = await api.auth.getMe();
                if (!cancelled && response.data) {
                    setUser(response.data);
                }
            } catch (err: any) {
                if (!cancelled && err.response?.status === 401) {
                    clearSession();
                    router.replace('/login');
                }
            } finally {
                // Always resolve loading — even if this run was "cancelled" by
                // StrictMode cleanup, the second run was blocked by the ref
                // guard so *this* run is the only one that can clear loading.
                setIsValidating(false);
                isValidatingRef.current = false;
            }
        };

        validateSession();
        return () => {
            cancelled = true;
        };
    }, [isAuthenticated, router, clearSession, setUser]);

    if (!isAuthenticated || isValidating) {
        return (
            <div className="min-h-screen bg-[var(--bg-base)] flex items-center justify-center">
                <div className="flex flex-col items-center gap-4">
                    <div className="w-10 h-10 bg-[var(--accent-primary)] rounded-lg animate-pulse" />
                    <p className="text-sm text-[var(--text-tertiary)]">Loading...</p>
                </div>
            </div>
        );
    }

    return <>{children}</>;
}
