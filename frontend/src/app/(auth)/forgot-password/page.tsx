'use client';

import { useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await api.auth.forgotPassword(email);
      setSent(true);
    } catch {
      setError('Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#f0eeea] flex items-center justify-center p-4">
      <div className="w-full max-w-sm bg-white rounded-2xl border border-[#dedad4] p-8 shadow-sm">
        {sent ? (
          <>
            <div className="w-10 h-10 bg-[#f0fdf4] border border-[#bbf7d0] rounded-xl flex items-center justify-center mx-auto mb-4">
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M4 10l4 4 8-8" stroke="#16a34a" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <h1 className="text-xl font-semibold text-[#1a1917] mb-2 text-center">Check your email</h1>
            <p className="text-sm text-[#6b6762] text-center mb-6">
              If <span className="font-medium text-[#1a1917]">{email}</span> is registered, you&apos;ll receive a reset link shortly. Check your spam folder if it doesn&apos;t arrive.
            </p>
            <Link href="/login">
              <Button variant="ghost" className="w-full">Back to sign in</Button>
            </Link>
          </>
        ) : (
          <>
            <h1 className="text-xl font-semibold text-[#1a1917] mb-1">Forgot password?</h1>
            <p className="text-sm text-[#6b6762] mb-6">Enter your email and we&apos;ll send you a reset link.</p>

            <form onSubmit={handleSubmit} className="space-y-4">
              <Input
                label="Email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
                required
              />

              {error && <p className="text-sm text-[#dc2626]">{error}</p>}

              <Button type="submit" className="w-full" loading={loading}>
                Send reset link
              </Button>
            </form>

            <p className="mt-5 text-center text-sm text-[#6b6762]">
              Remember it?{' '}
              <Link href="/login" className="text-[#1a1917] font-medium underline underline-offset-2">
                Sign in
              </Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
