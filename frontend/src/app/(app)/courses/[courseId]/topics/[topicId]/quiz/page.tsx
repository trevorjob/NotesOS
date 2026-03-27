'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function QuizPage() {
  const router = useRouter();

  useEffect(() => {
    // Topic-level quiz is deprecated — use the Generate Test page instead
    router.replace('/generate-test');
  }, [router]);

  return null;
}
