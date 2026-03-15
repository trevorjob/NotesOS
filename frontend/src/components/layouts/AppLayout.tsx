'use client';

import { Sidebar } from './Sidebar';
import { BottomNav } from './BottomNav';
import { AppTopBar } from './TopBar';
import { Crumb } from './Breadcrumb';
import { OfflineBanner } from '@/components/OfflineBanner';

interface AppLayoutProps {
  children: React.ReactNode;
  breadcrumb?: Crumb[];
  unreadCount?: number;
}

export function AppLayout({ children, breadcrumb = [], unreadCount = 0 }: AppLayoutProps) {
  return (
    <div className="min-h-screen bg-[var(--bg-base)]">
      <Sidebar />

      <AppTopBar breadcrumb={breadcrumb} unreadCount={unreadCount} />

      <main
        className="
          pt-[60px]
          pb-[80px] lg:pb-6
          lg:pl-[64px]
          min-h-screen
        "
      >
        <OfflineBanner />
        {children}
      </main>

      <BottomNav />
    </div>
  );
}
