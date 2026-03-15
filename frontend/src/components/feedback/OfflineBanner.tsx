'use client';

import { useEffect, useState } from 'react';
import { Icon } from '@/components/ui/Icon';

export function OfflineBanner() {
  const [isOnline, setIsOnline] = useState(true);
  const [wasOffline, setWasOffline] = useState(false);
  const [showRestored, setShowRestored] = useState(false);

  useEffect(() => {
    const online = () => {
      setIsOnline(true);
      if (wasOffline) {
        setShowRestored(true);
        setTimeout(() => { setShowRestored(false); setWasOffline(false); }, 3000);
      }
    };
    const offline = () => {
      setIsOnline(false);
      setWasOffline(true);
    };

    window.addEventListener('online', online);
    window.addEventListener('offline', offline);
    setIsOnline(navigator.onLine);
    return () => {
      window.removeEventListener('online', online);
      window.removeEventListener('offline', offline);
    };
  }, [wasOffline]);

  if (isOnline && !showRestored) return null;

  return (
    <div
      className={`flex items-center justify-center gap-2 px-4 py-2.5 text-xs font-semibold ${
        showRestored
          ? 'bg-[var(--success-bg)] text-[var(--success-text)]'
          : 'bg-amber-50 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300'
      }`}
    >
      <Icon name={showRestored ? 'wifi' : 'wifi_off'} size="xs" />
      {showRestored ? 'Connection restored' : 'No internet connection — working offline'}
    </div>
  );
}
