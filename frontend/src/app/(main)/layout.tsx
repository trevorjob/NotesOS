import { AuthGuard } from '@/components/AuthGuard';
import { AppLayout } from '@/components/layouts/AppLayout';

export default function MainGroupLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard>
      <AppLayout>{children}</AppLayout>
    </AuthGuard>
  );
}
