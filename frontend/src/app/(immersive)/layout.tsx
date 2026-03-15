import { AuthGuard } from '@/components/AuthGuard';
import { ImmersiveLayout } from '@/components/layouts/ImmersiveLayout';

export default function ImmersiveGroupLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard>
      <ImmersiveLayout>{children}</ImmersiveLayout>
    </AuthGuard>
  );
}
