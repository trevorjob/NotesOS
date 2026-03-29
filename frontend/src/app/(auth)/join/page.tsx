'use client';

import { Suspense, useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import { useSemesterStore } from '@/stores/semesters';
import { Button } from '@/components/ui/Button';

export default function JoinPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-[#f0eeea] flex items-center justify-center">
        <div className="w-5 h-5 border-2 border-[#1a1917] border-t-transparent rounded-full animate-spin" />
      </div>
    }>
      <JoinPageInner />
    </Suspense>
  );
}

function JoinPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const code = searchParams.get('code');

  const { isAuthenticated } = useAuthStore();
  const { joinSemester } = useSemesterStore();

  const joinAttempted = useRef(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!code) { router.replace('/home'); return; }
    if (!isAuthenticated || joinAttempted.current) return;
    joinAttempted.current = true;

    joinSemester(code)
      .then(() => router.replace('/home'))
      .catch((e: unknown) => {
        const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        if (detail === 'Already a member of this semester.') {
          router.replace('/home');
        } else {
          setError(detail || 'Invalid invite link.');
        }
      });
  }, [isAuthenticated, code, joinSemester, router]);

  if (isAuthenticated && !error) {
    return (
      <div className="min-h-screen bg-[#f0eeea] flex items-center justify-center">
        <div className="w-5 h-5 border-2 border-[#1a1917] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!code) return null;

  const registerHref = `/register?code=${encodeURIComponent(code)}`;
  const loginHref = `/login?redirect=${encodeURIComponent(`/join?code=${code}`)}`;

  return (
    <div className="min-h-screen bg-[#f0eeea] flex items-center justify-center p-4">
      <div className="w-full max-w-sm bg-white rounded-2xl border border-[#dedad4] p-8 shadow-sm text-center">
        <div className="w-10 h-10 bg-[#1a1917] rounded-xl flex items-center justify-center mx-auto mb-4">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M10 2L3 7v11h5v-5h4v5h5V7l-7-5z" stroke="white" strokeWidth="1.5" strokeLinejoin="round"/>
          </svg>
        </div>

        <h1 className="text-xl font-semibold text-[#1a1917] mb-1">{"You've been invited"}</h1>
        <p className="text-sm text-[#6b6762] mb-6">Join a semester on NotesOS and get access to all its courses.</p>

        {error && <p className="text-sm text-[#dc2626] mb-4">{error}</p>}

        {!error && (
          <div className="flex flex-col gap-2">
            <Button className="w-full" onClick={() => router.push(registerHref)}>
              Create account
            </Button>
            <Button variant="ghost" className="w-full" onClick={() => router.push(loginHref)}>
              Sign in
            </Button>
          </div>
        )}

        {error && (
          <Button variant="ghost" className="w-full mt-2" onClick={() => router.replace('/home')}>
            Go to home
          </Button>
        )}
      </div>
    </div>
  );
}
