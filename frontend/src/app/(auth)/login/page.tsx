'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirect = searchParams.get('redirect');
  const { login, isLoading, error, clearError } = useAuthStore();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    clearError();
    try {
      await login(email, password);
      const dest = redirect && redirect.startsWith('/') ? redirect : '/home';
      router.replace(dest);
    } catch {
      // error already in store
    }
  }

  return (
    <div className="min-h-screen bg-[#f0eeea] flex items-center justify-center p-4">
      <div className="w-full max-w-sm bg-white rounded-2xl border border-[#dedad4] p-8 shadow-sm">
        <h1 className="text-xl font-semibold text-[#1a1917] mb-1">Welcome back</h1>
        <p className="text-sm text-[#6b6762] mb-6">Sign in to continue studying</p>

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
          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            autoComplete="current-password"
            required
          />

          {error && (
            <p className="text-sm text-[#dc2626]">{error}</p>
          )}

          <Button type="submit" className="w-full" loading={isLoading}>
            Sign in
          </Button>
        </form>

        <p className="mt-5 text-center text-sm text-[#6b6762]">
          No account?{' '}
          <Link href="/register" className="text-[#1a1917] font-medium underline underline-offset-2">
            Create one
          </Link>
        </p>
      </div>
    </div>
  );
}
