import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { AppState, AppStateStatus } from 'react-native';
import { usePathname } from 'expo-router';
import { getAccessToken } from '@/lib/auth';
import { fetchMe } from '@/lib/profile';
import { fetchUnreadCount, NotificationItem } from '@/lib/notifications';
import { UserSocket } from '@/lib/userSocket';

// App-wide notifications context: owns the single /ws/user/{id} connection (live push,
// see notifications-plan.md §2 "Lane 1") and the unread badge count shown on the home
// bell. Mounted once at root (RootLayout), like ThemeProvider/QuickSwitcherProvider.
//
// Connection lifecycle is auth- and AppState-driven rather than screen-driven (unlike
// CourseSocket, which a single screen opens/closes): routes don't expose a login/logout
// event, so this watches `pathname` — landing away from /login or / (the pre-auth routes)
// after having a token means "just authed"; landing back on /login means "just signed out".
const PRE_AUTH_ROUTES = new Set(['/login', '/']);

interface NotificationsContextValue {
  unreadCount: number;
  refreshUnreadCount: () => Promise<void>;
  markAllReadLocally: () => void;
  markOneReadLocally: () => void;
  subscribeToLive: (listener: (item: NotificationItem) => void) => () => void;
}

const NotificationsContext = createContext<NotificationsContextValue | null>(null);

export function NotificationsProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  // Raw server-derived count; the exposed `unreadCount` also folds in "are we even
  // authed right now" (see below) so the pre-auth effect never has to setState itself.
  const [rawUnreadCount, setRawUnreadCount] = useState(0);
  const socketRef = useRef<UserSocket | null>(null);
  const listenersRef = useRef<Set<(item: NotificationItem) => void>>(new Set());
  const appState = useRef<AppStateStatus>(AppState.currentState);

  const refreshUnreadCount = useCallback(async () => {
    try {
      const count = await fetchUnreadCount();
      setRawUnreadCount(count);
    } catch {
      // Best-effort — the badge just won't update this pass.
    }
  }, []);

  const markAllReadLocally = useCallback(() => setRawUnreadCount(0), []);
  const markOneReadLocally = useCallback(() => setRawUnreadCount((n) => Math.max(0, n - 1)), []);

  const subscribeToLive = useCallback((listener: (item: NotificationItem) => void) => {
    listenersRef.current.add(listener);
    return () => listenersRef.current.delete(listener);
  }, []);

  const disconnectSocket = useCallback(() => {
    socketRef.current?.disconnect();
    socketRef.current = null;
  }, []);

  const connectSocket = useCallback(async () => {
    if (socketRef.current) return;
    const token = await getAccessToken();
    if (!token) return;

    let userId: string;
    try {
      userId = (await fetchMe()).id;
    } catch {
      return; // Not actually authed (stale/invalid token) — the api interceptor handles the redirect.
    }

    const socket = new UserSocket(userId, {
      // The initial unread-count fetch lives here rather than in this function's own body:
      // onOpen is a genuine "subscribe, then setState in the callback" per React's effect
      // guidance, whereas a setState-touching call directly in connectSocket's body would be
      // reachable straight from the effect that invokes connectSocket.
      onOpen: () => {
        void refreshUnreadCount();
      },
      onMessage: (message) => {
        if (message.type !== 'notification') return;
        const item = message.data as NotificationItem;
        setRawUnreadCount((n) => n + 1);
        listenersRef.current.forEach((listener) => listener(item));
      },
    });
    socketRef.current = socket;
    await socket.connect();
  }, [refreshUnreadCount]);

  // Auth transitions, inferred from route (see PRE_AUTH_ROUTES note above).
  useEffect(() => {
    if (PRE_AUTH_ROUTES.has(pathname)) {
      disconnectSocket();
      return;
    }
    void connectSocket();
  }, [pathname, connectSocket, disconnectSocket]);

  // AppState: RN drops sockets when backgrounded, so hold no connection while backgrounded
  // and reconnect fresh (with backoff reset) on foreground.
  useEffect(() => {
    const subscription = AppState.addEventListener('change', (next) => {
      const wasBackground = appState.current.match(/inactive|background/);
      if (next === 'background' || next === 'inactive') {
        disconnectSocket();
      } else if (next === 'active' && wasBackground && !PRE_AUTH_ROUTES.has(pathname)) {
        void connectSocket();
      }
      appState.current = next;
    });
    return () => subscription.remove();
  }, [pathname, connectSocket, disconnectSocket]);

  useEffect(() => disconnectSocket, [disconnectSocket]);

  const unreadCount = PRE_AUTH_ROUTES.has(pathname) ? 0 : rawUnreadCount;

  const value = useMemo(
    () => ({ unreadCount, refreshUnreadCount, markAllReadLocally, markOneReadLocally, subscribeToLive }),
    [unreadCount, refreshUnreadCount, markAllReadLocally, markOneReadLocally, subscribeToLive]
  );

  return <NotificationsContext.Provider value={value}>{children}</NotificationsContext.Provider>;
}

export function useNotifications() {
  const ctx = useContext(NotificationsContext);
  if (!ctx) throw new Error('useNotifications must be used within NotificationsProvider');
  return ctx;
}
