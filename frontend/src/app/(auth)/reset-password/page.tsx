'use client';

import { FormEvent, Suspense, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { PasswordInput } from '@/components/ui/PasswordInput';
import { Button } from '@/components/ui/Button';
import { TextLink } from '@/components/ui/TextLink';
import { Icon } from '@/components/ui/Icon';
import { apiClient } from '@/lib/api';

type PageState = 'idle' | 'loading' | 'success' | 'invalid';

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get('token') ?? '';

  const [password, setPassword]   = useState('');
  const [confirm, setConfirm]     = useState('');
  const [state, setState]         = useState<PageState>(token ? 'idle' : 'invalid');
  const [error, setError]         = useState('');

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');

    if (password.length < 8) {
      setError('Password must be at least 8 characters.');
      return;
    }
    if (password !== confirm) {
      setError('Passwords do not match.');
      return;
    }

    setState('loading');
    try {
      await apiClient.post('/api/auth/reset-password', {
        token,
        new_password: password,
      });
      setState('success');
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? 'Invalid or expired reset link.';
      setError(msg);
      if (err?.response?.status === 400) {
        setState('invalid');
      } else {
        setState('idle');
      }
    }
  };

  if (state === 'invalid') {
    return (
      <div className="glass-card p-8 text-center">
        <div className="w-14 h-14 rounded-2xl bg-[var(--error-bg)] flex items-center justify-center mx-auto mb-4">
          <Icon name="link_off" size="lg" className="text-[var(--color-error)]" />
        </div>
        <h1 className="font-display font-semibold text-xl text-[var(--text-primary)] mb-2">
          Link expired or invalid
        </h1>
        <p className="text-sm text-[var(--text-secondary)] mb-8">
          This reset link is no longer valid. Request a new one.
        </p>
        <Button
          variant="primary"
          size="md"
          onClick={() => router.push('/forgot-password')}
        >
          Request new link
        </Button>
      </div>
    );
  }

  if (state === 'success') {
    return (
      <div className="glass-card p-8 text-center">
        <div className="w-14 h-14 rounded-2xl bg-[var(--success-bg)] flex items-center justify-center mx-auto mb-4">
          <Icon name="check_circle" size="lg" className="text-[var(--color-success)]" />
        </div>
        <h1 className="font-display font-semibold text-xl text-[var(--text-primary)] mb-2">
          Password updated
        </h1>
        <p className="text-sm text-[var(--text-secondary)] mb-8">
          Your password has been reset. Sign in with your new password.
        </p>
        <Button variant="primary" size="md" onClick={() => router.push('/login')}>
          Sign in
        </Button>
      </div>
    );
  }

  return (
    <div className="glass-card p-8">
      <h1 className="font-display font-semibold text-2xl text-[var(--text-primary)] mb-1">
        Set new password
      </h1>
      <p className="text-sm text-[var(--text-secondary)] mb-8">
        Choose a strong password you haven't used before.
      </p>

      {error && (
        <div className="mb-6 flex items-start gap-2 px-4 py-3 bg-[var(--error-bg)] rounded-xl">
          <Icon name="error" size="xs" className="text-[var(--color-error)] flex-shrink-0 mt-0.5" />
          <p className="text-sm text-[var(--error-text)]">{error}</p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-5">
        <PasswordInput
          label="New password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          autoComplete="new-password"
        />
        <PasswordInput
          label="Confirm new password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
          autoComplete="new-password"
        />
        <Button
          type="submit"
          variant="primary"
          size="lg"
          loading={state === 'loading'}
          fullWidth
        >
          Reset password
        </Button>
      </form>

      <p className="text-center text-sm text-[var(--text-secondary)] mt-6">
        <TextLink href="/login">Back to sign in</TextLink>
      </p>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<div className="glass-card p-8 animate-pulse h-64" />}>
      <ResetPasswordForm />
    </Suspense>
  );
}
