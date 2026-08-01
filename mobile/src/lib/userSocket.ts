import { getAccessToken } from '@/lib/auth';
import { ReconnectingSocket, SocketCallbacks, WS_BASE_URL } from '@/lib/wsClient';

// User-scoped WebSocket client: WS /ws/user/{user_id}?token=…. Personal channel — not a
// course room — for live-pushed notifications (services/notifications.py publishes here
// via Redis `user_notifications`). Messages arrive as {type: 'notification', data: {...}}.
// Owned by NotificationsProvider (components/notifications/), which is AppState-aware —
// this class just manages the socket, not when the app should hold one open.

export type UserSocketCallbacks = SocketCallbacks;

export class UserSocket extends ReconnectingSocket {
  private readonly userId: string;

  constructor(userId: string, callbacks: UserSocketCallbacks) {
    super(callbacks);
    this.userId = userId;
  }

  protected async buildUrl(): Promise<string | null> {
    const token = await getAccessToken();
    if (!token) return null;
    return `${WS_BASE_URL}/ws/user/${this.userId}?token=${encodeURIComponent(token)}`;
  }
}
