/**
 * NotesOS - Auth Layout
 * Wraps login/register: redirects to /courses if already authenticated.
 */

import { AuthRedirect } from '@/components/AuthRedirect';

export default function AuthLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return <AuthRedirect>{children}</AuthRedirect>;
}
