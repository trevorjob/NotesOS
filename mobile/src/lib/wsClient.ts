import { API_BASE_URL } from '@/lib/api';

// Shared reconnecting-WebSocket scaffold: heartbeat, backoff reconnect, 1008=auth-stop.
// Subclasses (CourseSocket, UserSocket) only need to supply the room-specific URL.
// Extracted so the two client sockets don't duplicate connection lifecycle logic.

export const WS_BASE_URL = API_BASE_URL.replace(/^http/, 'ws');
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_BASE_DELAY_MS = 1000;
const HEARTBEAT_INTERVAL_MS = 30_000;
const PONG_TIMEOUT_MS = 10_000;

export interface SocketCallbacks {
  onMessage?: (message: { type?: string } & Record<string, unknown>) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: unknown) => void;
}

export abstract class ReconnectingSocket {
  private ws: WebSocket | null = null;
  protected readonly callbacks: SocketCallbacks;
  private reconnectAttempts = 0;
  private intentionalClose = false;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private pongTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(callbacks: SocketCallbacks) {
    this.callbacks = callbacks;
  }

  /** Build the fully-qualified `wss://…?token=…` URL, or null if there's no auth token. */
  protected abstract buildUrl(): Promise<string | null>;

  async connect(): Promise<void> {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) return;

    const url = await this.buildUrl();
    if (!url) {
      this.callbacks.onError?.(new Error('No auth token for WebSocket'));
      return;
    }

    this.intentionalClose = false;

    try {
      const ws = new WebSocket(url);
      this.ws = ws;

      ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.startHeartbeat();
        this.callbacks.onOpen?.();
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data as string) as { type?: string } & Record<string, unknown>;
          if (message.type === 'pong') {
            this.clearPongTimer();
            return;
          }
          this.callbacks.onMessage?.(message);
        } catch {
          // Ignore unparseable frames — the server only sends JSON.
        }
      };

      ws.onerror = (error) => this.callbacks.onError?.(error);

      ws.onclose = (event) => {
        this.stopHeartbeat();
        this.callbacks.onClose?.();
        // 1008 = auth rejected; reconnecting won't fix a bad/expired token.
        if (event.code === 1008 || this.intentionalClose) return;
        if (this.reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
          this.reconnectAttempts += 1;
          const delay = RECONNECT_BASE_DELAY_MS * 2 ** (this.reconnectAttempts - 1);
          this.reconnectTimer = setTimeout(() => {
            void this.connect();
          }, delay);
        }
      };
    } catch (error) {
      this.callbacks.onError?.(error);
    }
  }

  disconnect(): void {
    this.intentionalClose = true;
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  /** Reset backoff so the next `connect()` retries immediately (e.g. app foregrounded). */
  resetBackoff(): void {
    this.reconnectAttempts = 0;
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.pingTimer = setInterval(() => {
      if (this.ws?.readyState !== WebSocket.OPEN) return;
      this.ws.send(JSON.stringify({ type: 'ping' }));
      this.pongTimer = setTimeout(() => this.ws?.close(), PONG_TIMEOUT_MS);
    }, HEARTBEAT_INTERVAL_MS);
  }

  private stopHeartbeat(): void {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
    this.clearPongTimer();
  }

  private clearPongTimer(): void {
    if (this.pongTimer) {
      clearTimeout(this.pongTimer);
      this.pongTimer = null;
    }
  }
}
