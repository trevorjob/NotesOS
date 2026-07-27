import { API_BASE_URL } from '@/lib/api';
import { getAccessToken } from '@/lib/auth';

// Minimal course-room WebSocket client. This is the first WS surface on mobile (the
// broader notifications/presence work is §2.9) — kept deliberately small: connect to
// WS /ws/{course_id}?token=…, hand parsed messages to onMessage, heartbeat, and
// reconnect with backoff unless the close was intentional or an auth rejection (1008).
// Mirrors frontend/src/lib/websocket.ts, trimmed to what capture needs.

const WS_BASE_URL = API_BASE_URL.replace(/^http/, 'ws');
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_BASE_DELAY_MS = 1000;
const HEARTBEAT_INTERVAL_MS = 30_000;
const PONG_TIMEOUT_MS = 10_000;

export interface CourseSocketCallbacks {
  onMessage?: (message: { type?: string } & Record<string, unknown>) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: unknown) => void;
}

export class CourseSocket {
  private ws: WebSocket | null = null;
  private readonly courseId: string;
  private readonly callbacks: CourseSocketCallbacks;
  private reconnectAttempts = 0;
  private intentionalClose = false;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private pingTimer: ReturnType<typeof setInterval> | null = null;
  private pongTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(courseId: string, callbacks: CourseSocketCallbacks) {
    this.courseId = courseId;
    this.callbacks = callbacks;
  }

  async connect(): Promise<void> {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) return;

    const token = await getAccessToken();
    if (!token) {
      this.callbacks.onError?.(new Error('No auth token for WebSocket'));
      return;
    }

    const url = `${WS_BASE_URL}/ws/${this.courseId}?token=${encodeURIComponent(token)}`;
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
