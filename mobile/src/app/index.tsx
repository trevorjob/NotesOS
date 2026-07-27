import { useEffect, useState } from 'react';
import { Redirect } from 'expo-router';
import { getAccessToken } from '@/lib/auth';

// Cold entry → home if a session is already stored, otherwise login.
export default function Index() {
  const [destination, setDestination] = useState<'/home' | '/login' | null>(null);

  useEffect(() => {
    getAccessToken().then((token) => setDestination(token ? '/home' : '/login'));
  }, []);

  if (!destination) return null;
  return <Redirect href={destination} />;
}
