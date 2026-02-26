/**
 * NotesOS - Offline Banner
 * Shown when the user loses network connectivity. Slides in/out smoothly.
 */

'use client';

import { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { WifiOff, Loader2, CheckCircle2 } from 'lucide-react';
import { useNetworkStore, attachNetworkListeners } from '@/stores/network';

export function OfflineBanner() {
    const { isOnline, isSyncing, lastSyncedAt } = useNetworkStore();

    // Attach browser event listeners on first render (client only)
    useEffect(() => {
        attachNetworkListeners();
    }, []);

    // Briefly show "synced" after reconnecting — handled by isSyncing going false
    const showSyncComplete = isOnline && !isSyncing && lastSyncedAt !== null;

    return (
        <AnimatePresence mode="wait">
            {/* Offline banner */}
            {!isOnline && (
                <motion.div
                    key="offline"
                    initial={{ opacity: 0, y: -40 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -40 }}
                    transition={{ duration: 0.25, ease: 'easeOut' }}
                    className="fixed top-0 left-0 right-0 z-[100] flex items-center justify-center gap-2.5 px-4 py-2.5 bg-amber-400/95 text-amber-950 text-sm font-medium backdrop-blur-sm shadow-md"
                    role="status"
                    aria-live="polite"
                >
                    <WifiOff className="w-4 h-4 shrink-0" />
                    <span>
                        You&apos;re offline. Notes are read-only.{' '}
                        <span className="font-normal opacity-80">Changes sync when online.</span>
                    </span>
                </motion.div>
            )}

            {/* Syncing banner */}
            {isOnline && isSyncing && (
                <motion.div
                    key="syncing"
                    initial={{ opacity: 0, y: -40 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -40 }}
                    transition={{ duration: 0.25, ease: 'easeOut' }}
                    className="fixed top-0 left-0 right-0 z-[100] flex items-center justify-center gap-2.5 px-4 py-2.5 bg-blue-500/90 text-white text-sm font-medium backdrop-blur-sm shadow-md"
                    role="status"
                    aria-live="polite"
                >
                    <Loader2 className="w-4 h-4 shrink-0 animate-spin" />
                    <span>Syncing changes…</span>
                </motion.div>
            )}
        </AnimatePresence>
    );
}
