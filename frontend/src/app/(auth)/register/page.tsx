/**
 * NotesOS - Register Page
 * Registrations are temporarily disabled.
 */

import Link from 'next/link';
import { GlassCard, Button } from '@/components/ui';

export default function RegisterPage() {
    return (
        <div className="min-h-screen bg-[var(--bg-base)] flex items-center justify-center px-4 py-12">
            <div className="w-full max-w-md">
                {/* Logo */}
                <div className="flex items-center justify-center gap-3 mb-12">
                    <div className="w-10 h-10 bg-[var(--accent-primary)] rounded-lg" />
                    <span className="text-2xl font-semibold text-[var(--text-primary)]">
                        NotesOS
                    </span>
                </div>

                {/* Disabled Message */}
                <GlassCard>
                    <div className="mb-8 text-center">
                        <h1 className="text-2xl font-semibold text-[var(--text-primary)] mb-2">
                            Registrations Closed
                        </h1>
                        <p className="text-sm text-[var(--text-tertiary)]">
                            We are not currently accepting new accounts.
                        </p>
                    </div>

                    <div className="flex justify-center">
                        <Link href="/login" className="w-full">
                            <Button
                                type="button"
                                variant="primary"
                                size="lg"
                                className="w-full"
                            >
                                Back to Sign in
                            </Button>
                        </Link>
                    </div>
                </GlassCard>
            </div>
        </div>
    );
}
