'use client';

import { useEffect, useState } from 'react';
import { TopNav } from './TopNav';
import { Sidebar } from './Sidebar';
import { useCourseStore } from '@/stores/courses';
import { useNotificationStore } from '@/stores/notifications';
import { ToastContainer } from '@/components/ui/Toast';

interface AppShellProps {
  children: React.ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const courses = useCourseStore((s) => s.courses);
  const initWebSocket = useNotificationStore((s) => s.initWebSocket);

  // Connect WebSocket to first available course for app-level notifications
  useEffect(() => {
    if (courses.length === 0) return;
    const cleanup = initWebSocket(courses[0].id);
    return cleanup;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [courses.length > 0 ? courses[0].id : null]);

  return (
    <div className="flex flex-col h-screen bg-[#f0eeea]">
      <TopNav onMenuClick={() => setDrawerOpen(true)} />

      <div className="flex flex-1 overflow-hidden relative">
        {/* Sidebar — permanent on md+, hidden on mobile */}
        <aside className="hidden md:flex shrink-0">
          <Sidebar />
        </aside>

        {/* Mobile drawer overlay */}
        {drawerOpen && (
          <>
            {/* Backdrop */}
            <div
              className="fixed inset-0 bg-black/40 z-40 md:hidden"
              onClick={() => setDrawerOpen(false)}
            />
            {/* Drawer */}
            <div className="fixed inset-y-0 left-0 z-50 md:hidden animate-slide-right">
              <Sidebar onClose={() => setDrawerOpen(false)} />
            </div>
          </>
        )}

        {/* Main content */}
        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>

      <ToastContainer />
    </div>
  );
}
