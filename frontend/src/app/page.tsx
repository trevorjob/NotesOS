import { redirect } from 'next/navigation';

// Root route: just redirect to the app home.
// The (app)/layout.tsx AuthGuard handles the login redirect if not authenticated.
export default function RootPage() {
  redirect('/home');
}
