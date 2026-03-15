'use client';

import { FormEvent, useState } from 'react';
import { TextInputBordered } from '@/components/ui/TextInputBordered';
import { Button } from '@/components/ui/Button';
import { TextLink } from '@/components/ui/TextLink';
import { Icon } from '@/components/ui/Icon';
import { apiClient } from '@/lib/api';

type PageState = 'idle' | 'loading' | 'submitted';

export default function ForgotPasswordPage() {
  const [email, setEmail]     = useState('');
  const [state, setState]     = useState<PageState>('idle');
  const [error, setError]     = useState('');

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setState('loading');
    try {
      await apiClient.post('/api/auth/forgot-password', { email });
    } catch {
      // Server always returns 200 — any failure is a network error
    } finally {
      setState('submitted');
    }
  };

  if (state === 'submitted') {
    return (
      <div className="glass-card p-8 text-center">
        <div className="w-14 h-14 rounded-2xl bg-[var(--success-bg)] flex items-center justify-center mx-auto mb-4">
          <Icon name="mark_email_read" size="lg" className="text-[var(--color-success)]" />
        </div>
        <h1 className="font-display font-semibold text-xl text-[var(--text-primary)] mb-2">
          Check your inbox
        </h1>
        <p className="text-sm text-[var(--text-secondary)] mb-8 max-w-[280px] mx-auto">
          If an account exists for <strong>{email}</strong>, we've sent a password reset link. It expires in 1 hour.
        </p>
        <TextLink href="/login">Back to sign in</TextLink>
      </div>
    );
  }

  return (
    <div className="glass-card p-8">
      <button
        onClick={() => history.back()}
        className="flex items-center gap-1.5 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors mb-6"
      >
        <Icon name="arrow_back" size="xs" /> Back
      </button>

      <h1 className="font-display font-semibold text-2xl text-[var(--text-primary)] mb-1">
        Forgot password?
      </h1>
      <p className="text-sm text-[var(--text-secondary)] mb-8">
        Enter your email and we'll send a reset link.
      </p>

      {error && (
        <div className="mb-6 flex items-start gap-2 px-4 py-3 bg-[var(--error-bg)] rounded-xl">
          <Icon name="error" size="xs" className="text-[var(--color-error)] flex-shrink-0 mt-0.5" />
          <p className="text-sm text-[var(--error-text)]">{error}</p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-5">
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
        <Button type="submit" variant="primary" size="lg" loading={state === 'loading'} fullWidth>
          Send reset link
        </Button>
      </form>

      <p className="text-center text-sm text-[var(--text-secondary)] mt-6">
        Remember it? <TextLink href="/login">Sign in</TextLink>
      </p>
    </div>
  );
}
