'use client';

import { Suspense, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { api } from '@/lib/api';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-[#f0eeea] flex items-center justify-center">
        <div className="w-5 h-5 border-2 border-[#1a1917] border-t-transparent rounded-full animate-spin" />
      </div>
    }>
      <ResetPasswordPageInner />
    </Suspense>
  );
}

function ResetPasswordPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get('token') ?? '';

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);

  if (!token) {
    return (
      <div className="min-h-screen bg-[#f0eeea] flex items-center justify-center p-4">
        <div className="w-full max-w-sm bg-white rounded-2xl border border-[#dedad4] p-8 shadow-sm text-center">
          <p className="text-sm text-[#6b6762] mb-4">This reset link is invalid or has expired.</p>
          <Link href="/forgot-password">
            <Button className="w-full">Request a new link</Button>
          </Link>
        </div>
      </div>
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    if (password.length < 8) { setError('Password must be at least 8 characters.'); return; }
    if (password !== confirm) { setError('Passwords do not match.'); return; }

    setLoading(true);
    try {
      await api.auth.resetPassword(token, password);
      setDone(true);
      setTimeout(() => router.replace('/login'), 2500);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || 'This link has expired. Please request a new one.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#f0eeea] flex items-center justify-center p-4">
      <div className="w-full max-w-sm bg-white rounded-2xl border border-[#dedad4] p-8 shadow-sm">
        {done ? (
          <>
            <div className="w-10 h-10 bg-[#f0fdf4] border border-[#bbf7d0] rounded-xl flex items-center justify-center mx-auto mb-4">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M4 10l4 4 8-8" stroke="#16a34a" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <h1 className="text-xl font-semibold text-[#1a1917] mb-2 text-center">Password updated</h1>
            <p className="text-sm text-[#6b6762] text-center">Redirecting you to sign in…</p>
          </>
        ) : (
          <>
            <h1 className="text-xl font-semibold text-[#1a1917] mb-1">Set new password</h1>
            <p className="text-sm text-[#6b6762] mb-6">Choose a strong password for your account.</p>

            <form onSubmit={handleSubmit} className="space-y-4">
              <Input
                label="New password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Min. 8 characters"
                autoComplete="new-password"
                required
              />
              <Input
                label="Confirm password"
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="Repeat your password"
                autoComplete="new-password"
                required
              />

              {error && <p className="text-sm text-[#dc2626]">{error}</p>}

              <Button type="submit" className="w-full" loading={loading}>
                Update password
              </Button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
