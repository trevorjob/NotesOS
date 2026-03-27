'use client';

import { useEffect } from 'react';
import { attachNetworkListeners } from '@/stores/network';

export function Providers({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    attachNetworkListeners();
  }, []);

  return <>{children}</>;
}
