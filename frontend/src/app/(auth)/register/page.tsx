/**
 * NotesOS - Register Page
 * Glass form with warm palette
 */

'use client';

import { useState, FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuthStore } from '@/stores/auth';
import { GlassCard, Input, Button } from '@/components/ui';

export default function RegisterPage() {
    const router = useRouter();
    const { register, isLoading, error, clearError } = useAuthStore();

    const [fullName, setFullName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        clearError();

        try {
            await register({
                full_name: fullName,
                email,
                password,
            });
            router.push('/courses');
        } catch (err) {
            // Error is already set in store
            console.error('Registration failed:', err);
        }
    };

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

                {/* Register Form */}
                <GlassCard>
                    <div className="mb-8">
                        <h1 className="text-2xl font-semibold text-[var(--text-primary)] mb-2">
                            Create your account
                        </h1>
                        <p className="text-sm text-[var(--text-tertiary)]">
                            Start studying smarter, together
                        </p>
                    </div>

                    {error && (
                        <div className="mb-6 px-4 py-3 bg-[var(--error)]/10 border border-[var(--error)]/20 rounded-lg">
                            <p className="text-sm text-[var(--error)]">{error}</p>
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-5">
                        <Input
                            label="Full name"
                            type="text"
                            placeholder="Sarah Kim"
                            value={fullName}
                            onChange={(e) => setFullName(e.target.value)}
                            required
                            autoComplete="name"
                        />

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
                            autoComplete="new-password"
                        />
                        {/* 
                        <Input
                            label="University (optional)"
                            type="text"
                            placeholder="Stanford University"
                            value={university}
                            onChange={(e) => setUniversity(e.target.value)}
                            autoComplete="organization"
                        /> */}

                        <Button
                            type="submit"
                            variant="primary"
                            size="lg"
                            className="w-full"
                            disabled={isLoading}
                        >
                            {isLoading ? 'Creating account...' : 'Create account'}
                        </Button>
                    </form>

                    <div className="mt-6 text-center">
                        <p className="text-sm text-[var(--text-tertiary)]">
                            Already have an account?{' '}
                            <Link
                                href="/login"
                                className="text-[var(--accent-primary)] hover:text-[var(--accent-hover)] font-medium transition-colors"
                            >
                                Sign in
                            </Link>
                        </p>
                    </div>
                </GlassCard>

                {/* Footer */}
                <p className="mt-8 text-center text-xs text-[var(--text-tertiary)]">
                    By signing up, you agree to our Terms and Privacy Policy
                </p>
            </div>
        </div>
    );
}
