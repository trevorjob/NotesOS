import type { Metadata, Viewport } from 'next';
import './globals.css';
import { Providers } from '@/components/Providers';
import { PostHogProvider } from '@/components/PostHogProvider';

export const metadata: Metadata = {
  title: 'NotesOS',
  description: 'Study smarter, together. Your notes, your AI, your success.',
  manifest: '/manifest.json',
};

export const viewport: Viewport = {
  themeColor: '#1a1917',
  width: 'device-width',
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <PostHogProvider>
          <Providers>{children}</Providers>
        </PostHogProvider>
      </body>
    </html>
  );
}
