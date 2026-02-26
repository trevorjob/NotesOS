/**
 * NotesOS - Network Status Store
 * Tracks online/offline status and sync state.
 */

'use client';

import { create } from 'zustand';

interface NetworkState {
    isOnline: boolean;
    isSyncing: boolean;
    lastSyncedAt: number | null;

    setOnline: (online: boolean) => void;
    setSyncing: (syncing: boolean) => void;
    setLastSyncedAt: (ts: number) => void;
}

export const useNetworkStore = create<NetworkState>((set) => ({
    // Init from navigator.onLine (false on SSR → we fix it in useEffect)
    isOnline: typeof window !== 'undefined' ? navigator.onLine : true,
    isSyncing: false,
    lastSyncedAt: null,

    setOnline: (online) => set({ isOnline: online }),
    setSyncing: (syncing) => set({ isSyncing: syncing }),
    setLastSyncedAt: (ts) => set({ lastSyncedAt: ts }),
}));

// ─── Global listener (call once from a Client Component or layout) ────────────

let listenerAttached = false;

export function attachNetworkListeners(): void {
    if (typeof window === 'undefined' || listenerAttached) return;
    listenerAttached = true;

    const store = useNetworkStore.getState();

    const handleOnline = () => {
        store.setOnline(true);
    };

    const handleOffline = () => {
        store.setOnline(false);
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // Sync initial state (navigator.onLine may have changed since store init)
    store.setOnline(navigator.onLine);
}
