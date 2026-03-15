import { AuthRedirect } from '@/components/AuthRedirect';
import { AuthLayout } from '@/components/layouts/AuthLayout';

export default function AuthGroupLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthRedirect>
      <AuthLayout>{children}</AuthLayout>
    </AuthRedirect>
  );
}
