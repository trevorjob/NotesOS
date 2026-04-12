'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth';
import { AppShell } from '@/components/layout/AppShell';
import { ErrorBoundary } from '@/components/ErrorBoundary';

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  // Wait for Zustand to rehydrate from localStorage before checking auth.
  // On the first render the persisted state hasn't loaded yet, so
  // isAuthenticated is briefly false even for a logged-in user.
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    // useAuthStore.persist.hasHydrated() is true synchronously after the first
    // effect tick once zustand has read localStorage.
    const unsub = useAuthStore.persist.onFinishHydration(() => {
      setHydrated(true);
    });
    // In case hydration already finished before we subscribed
    if (useAuthStore.persist.hasHydrated()) {
      setHydrated(true);
    }
    return unsub;
  }, []);

  useEffect(() => {
    if (hydrated && !isAuthenticated) {
      router.replace('/login');
    }
  }, [hydrated, isAuthenticated, router]);

  // Still hydrating — show nothing to avoid flash
  if (!hydrated) return null;

  if (!isAuthenticated) return null;

  return (
    <ErrorBoundary>
      <AppShell>{children}</AppShell>
    </ErrorBoundary>
  );
}
