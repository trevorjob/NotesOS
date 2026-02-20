/**
 * Profile & Settings Page
 * User info and study personality
 */

'use client';

import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import { MainLayout } from '@/components/layout';
import { GlassCard, Button } from '@/components/ui';
import { PersonalitySettings } from '@/components/PersonalitySettings';

export default function ProfilePage() {
    const router = useRouter();
    const { user, logout } = useAuthStore();

    const handleLogout = async () => {
        await logout();
        router.push('/login');
    };

    return (
        <MainLayout>
            <div className="max-w-2xl mx-auto px-8 md:px-20 py-12">
                <h1 className="text-2xl font-semibold text-[var(--text-primary)] mb-8">Profile</h1>

                <GlassCard className="mb-8">
                    <h2 className="text-lg font-medium text-[var(--text-primary)] mb-4">Account</h2>
                    <dl className="space-y-2">
                        <div>
                            <dt className="text-xs text-[var(--text-tertiary)]">Name</dt>
                            <dd className="text-[var(--text-primary)]">{user?.full_name ?? '—'}</dd>
                        </div>
                        <div>
                            <dt className="text-xs text-[var(--text-tertiary)]">Email</dt>
                            <dd className="text-[var(--text-primary)]">{user?.email ?? '—'}</dd>
                        </div>
                    </dl>
                </GlassCard>

                <div className="mb-8">
                    <PersonalitySettings />
                </div>

                <GlassCard>
                    <Button variant="secondary" onClick={handleLogout}>
                        Sign out
                    </Button>
                </GlassCard>
            </div>
        </MainLayout>
    );
}
