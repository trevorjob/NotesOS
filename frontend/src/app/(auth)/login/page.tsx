/**
 * NotesOS - Login Page
 * Glass form with warm palette
 */

'use client';

import { useState, FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuthStore } from '@/stores/auth';
import { GlassCard, Input, Button } from '@/components/ui';

export default function LoginPage() {
    const router = useRouter();
    const { login, isLoading, error, clearError } = useAuthStore();

    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        clearError();

        try {
            await login(email, password);
            router.push('/'); // Redirect to home (course home)
        } catch (err) {
            // Error is already set in store
            console.error('Login failed:', err);
        }
    };

    return (
        <div className="min-h-screen bg-[var(--bg-base)] flex items-center justify-center px-4">
            <div className="w-full max-w-md">
                {/* Logo */}
                <div className="flex items-center justify-center gap-3 mb-12">
                    <div className="w-10 h-10 bg-[var(--accent-primary)] rounded-lg" />
                    <span className="text-2xl font-semibold text-[var(--text-primary)]">
                        NotesOS
                    </span>
                </div>

                {/* Login Form */}
                <GlassCard>
                    <div className="mb-8">
                        <h1 className="text-2xl font-semibold text-[var(--text-primary)] mb-2">
                            Welcome back
                        </h1>
                        <p className="text-sm text-[var(--text-tertiary)]">
                            Sign in to continue studying
                        </p>
                    </div>

                    {error && (
                        <div className="mb-6 px-4 py-3 bg-[var(--error)]/10 border border-[var(--error)]/20 rounded-lg">
                            <p className="text-sm text-[var(--error)]">{error}</p>
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-5">
                        <Input
                            label="Email"
                            type="email"
                            placeholder="you@university.edu"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            required
                            autoComplete="email"
                        />

                        <Input
                            label="Password"
                            type="password"
                            placeholder="••••••••"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                            autoComplete="current-password"
                        />

                        <Button
                            type="submit"
                            variant="primary"
                            size="lg"
                            className="w-full"
                            disabled={isLoading}
                        >
                            {isLoading ? 'Signing in...' : 'Sign in'}
                        </Button>
                    </form>

                    <div className="mt-6 text-center">
                        <p className="text-sm text-[var(--text-tertiary)]">
                            Don't have an account?{' '}
                            <Link
                                href="/register"
                                className="text-[var(--accent-primary)] hover:text-[var(--accent-hover)] font-medium transition-colors"
                            >
                                Sign up
                            </Link>
                        </p>
                    </div>
                </GlassCard>

                {/* Footer */}
                <p className="mt-8 text-center text-xs text-[var(--text-tertiary)]">
                    Study smarter, together
                </p>
            </div>
        </div>
    );
}
