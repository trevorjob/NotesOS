/**
 * NotesOS - Main Layout
 * Wraps all authenticated routes (courses, etc.) with auth guard and session validation.
 */

import { AuthGuard } from '@/components/AuthGuard';
import { OfflineBanner } from '@/components/OfflineBanner';

export default function MainLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <AuthGuard>
            <OfflineBanner />
            {children}
        </AuthGuard>
    );
}
