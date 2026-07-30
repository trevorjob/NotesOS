import { useEffect, useRef } from 'react';
import { CourseSocket } from '@/lib/courseSocket';

// Realtime generation status for an authored test. The practice_test_worker already broadcasts
// per-question progress + completion over the course room (WS /ws/{course_id}) — so we subscribe
// instead of polling. Events (see workers/practice_test_worker.py):
//   practice_test_progress { test_id, done, total }
//   practice_test_complete { test_id, total }
//   practice_test_failed   { test_id, reason }

interface Handlers {
  onOpen?: () => void;
  onProgress?: (done: number, total: number) => void;
  onComplete?: (total: number) => void;
  onFailed?: (reason: string) => void;
}

export function usePracticeTestSocket(
  courseId: string | undefined,
  testId: string | undefined,
  active: boolean,
  handlers: Handlers,
) {
  // Route handlers through a ref so the socket subscribes once per (course, test), not on every
  // render — the callbacks always see the latest closure without re-connecting.
  const ref = useRef(handlers);
  useEffect(() => {
    ref.current = handlers;
  });

  useEffect(() => {
    if (!active || !courseId || !testId) return;
    const socket = new CourseSocket(courseId, {
      onOpen: () => ref.current.onOpen?.(),
      onMessage: (m) => {
        if (m.test_id !== testId) return;
        if (m.type === 'practice_test_progress') ref.current.onProgress?.(Number(m.done), Number(m.total));
        else if (m.type === 'practice_test_complete') ref.current.onComplete?.(Number(m.total));
        else if (m.type === 'practice_test_failed') ref.current.onFailed?.(String(m.reason ?? 'generation error'));
      },
    });
    void socket.connect();
    return () => socket.disconnect();
  }, [active, courseId, testId]);
}
