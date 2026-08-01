import { useEffect, useState } from 'react';
import { Redirect } from 'expo-router';
import { getAccessToken } from '@/lib/auth';
import { registerForPushNotifications } from '@/lib/push';

// Cold entry → home if a session is already stored, otherwise login.
export default function Index() {
  const [destination, setDestination] = useState<'/home' | '/login' | null>(null);

  useEffect(() => {
    getAccessToken().then((token) => {
      setDestination(token ? '/home' : '/login');
      // Re-register on every cold start with an existing session — cheap (Expo caches
      // the token) and self-heals a device that lost its registration (reinstall, or the
      // best-effort unregister-before-delete race in settings.tsx's confirmDelete).
      if (token) void registerForPushNotifications();
    });
  }, []);

  if (!destination) return null;
  return <Redirect href={destination} />;
}
