/**
 * NotesOS - Main Layout
 * Wraps all authenticated routes (courses, etc.) with auth guard and session validation.
 */

import { AuthGuard } from '@/components/AuthGuard';

export default function MainLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return <AuthGuard>{children}</AuthGuard>;
}
