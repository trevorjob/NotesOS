'use client';

import { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import { TextInputBordered } from '@/components/ui/TextInputBordered';
import { PasswordInput } from '@/components/ui/PasswordInput';
import { Button } from '@/components/ui/Button';
import { TextLink } from '@/components/ui/TextLink';
import { Icon } from '@/components/ui/Icon';

export default function RegisterPage() {
  const router = useRouter();
  const { register, isLoading, error, clearError } = useAuthStore();

  const [fullName, setFullName]   = useState('');
  const [email, setEmail]         = useState('');
  const [password, setPassword]   = useState('');
  const [confirm, setConfirm]     = useState('');
  const [localError, setLocalError] = useState('');

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setLocalError('');
    clearError();

    if (password.length < 8) {
      setLocalError('Password must be at least 8 characters.');
      return;
    }
    if (password !== confirm) {
      setLocalError('Passwords do not match.');
      return;
    }

    try {
      await register({ email, password, full_name: fullName });
      router.push('/courses');
    } catch {}
  };

  const displayError = localError || error;

  return (
    <div className="glass-card p-8">
      <h1 className="font-display font-semibold text-2xl text-[var(--text-primary)] mb-1">
        Create your account
      </h1>
      <p className="text-sm text-[var(--text-secondary)] mb-8">
        Start studying smarter with AI
      </p>

      {displayError && (
        <div className="mb-6 flex items-start gap-2 px-4 py-3 bg-[var(--error-bg)] border border-[var(--color-error)]/20 rounded-xl">
          <Icon name="error" size="xs" className="text-[var(--color-error)] flex-shrink-0 mt-0.5" />
          <p className="text-sm text-[var(--error-text)]">{displayError}</p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-5">
        <TextInputBordered
          label="Full name"
          type="text"
          placeholder="Jane Smith"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          iconLeft="person"
          required
          autoComplete="name"
        />
        <TextInputBordered
          label="Email address"
          type="email"
          placeholder="you@university.edu"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          iconLeft="mail"
          required
          autoComplete="email"
        />
        <PasswordInput
          label="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          autoComplete="new-password"
        />
        <PasswordInput
          label="Confirm password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
          autoComplete="new-password"
        />

        <Button type="submit" variant="primary" size="lg" loading={isLoading} fullWidth className="mt-2">
          Create account
        </Button>
      </form>

      {/* Google OAuth */}
      <div className="flex items-center gap-3 my-6">
        <div className="flex-1 h-px bg-[var(--border-base)]" />
        <span className="text-xs text-[var(--text-tertiary)] uppercase tracking-wider">or</span>
        <div className="flex-1 h-px bg-[var(--border-base)]" />
      </div>

      <a
        href={`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/auth/google`}
        className="
          flex items-center justify-center gap-3 w-full h-11
          rounded-xl border border-[var(--border-base)]
          bg-[var(--bg-elevated)] hover:bg-[var(--bg-sunken)]
          text-sm font-semibold text-[var(--text-primary)]
          transition-colors focus-ring
        "
      >
        <svg className="w-4 h-4" viewBox="0 0 24 24">
          <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
          <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
          <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
          <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
        </svg>
        Continue with Google
      </a>

      <p className="text-center text-sm text-[var(--text-secondary)] mt-6">
        Already have an account?{' '}
        <TextLink href="/login">Sign in</TextLink>
      </p>
    </div>
  );
}
