/**
 * NotesOS - WebSocket Client
 * Real-time updates for course resources, fact checks, and grading
 */

import { tokenManager } from './api';

export type WebSocketMessage =
    | { type: 'processing_status'; resource_id: string; status: 'processing' | 'completed' | 'failed' }
    | { type: 'fact_check:complete'; data: { resource_id: string; topic_id: string; summary: string; stats: Record<string, number> } }
    | { type: 'grading:complete'; data: { answer_id: string; attempt_id: string; score: number; encouragement: string } }
    | { type: 'knowledge_updated'; topic_id: string; knowledge_id: string }
    | { type: 'knowledge_status'; topic_id: string; status: string }
    | { type: 'notification'; data: { id: string; type: string; title: string; body: string; is_read: boolean; created_at: string; meta_data?: Record<string, string> } }
    | { type: 'resource_created'; data: unknown }
    | { type: 'resource_updated'; data: unknown }
    | { type: 'resource_deleted'; resource_id: string }
    | { type: 'user_joined'; user_id: string; timestamp: string | null }
    | { type: 'active_users'; users: string[] }
    | { type: 'ping' }
    | { type: 'pong' }
    | { type: 'echo'; data: unknown };

export interface WebSocketCallbacks {
    onMessage?: (message: WebSocketMessage) => void;
    onOpen?: () => void;
    onClose?: () => void;
    onError?: (error: Event) => void;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const WS_BASE_URL = API_BASE_URL.replace(/^http/, 'ws');

export class WebSocketClient {
    private ws: WebSocket | null = null;
    private courseId: string;
    private callbacks: WebSocketCallbacks;
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 5;
    private reconnectDelay = 1000;
    private reconnectTimer: NodeJS.Timeout | null = null;
    private isIntentionalClose = false;
    private pingTimer: NodeJS.Timeout | null = null;
    private pongTimer: NodeJS.Timeout | null = null;

    constructor(courseId: string, callbacks: WebSocketCallbacks) {
        this.courseId = courseId;
        this.callbacks = callbacks;
    }

    connect(): void {
        if (this.ws?.readyState === WebSocket.OPEN) {
            return; // Already connected
        }

        const token = tokenManager.getToken();
        if (!token) {
            console.error('[WebSocket] No token available');
            this.callbacks.onError?.(new Event('no_token'));
            return;
        }

        const wsUrl = `${WS_BASE_URL}/ws/${this.courseId}?token=${encodeURIComponent(token)}`;
        console.log('[WebSocket] Connecting to', wsUrl.replace(token, '***'));

        try {
            this.ws = new WebSocket(wsUrl);
            this.isIntentionalClose = false;

            this.ws.onopen = () => {
                console.log('[WebSocket] Connected');
                this.reconnectAttempts = 0;
                this._startHeartbeat();
                this.callbacks.onOpen?.();
            };

            this.ws.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data) as WebSocketMessage;
                    if (message.type === 'pong') {
                        // Clear the pong timeout — connection is alive
                        if (this.pongTimer) { clearTimeout(this.pongTimer); this.pongTimer = null; }
                        return;
                    }
                    this.callbacks.onMessage?.(message);
                } catch (err) {
                    console.error('[WebSocket] Failed to parse message:', err);
                }
            };

            this.ws.onerror = (error) => {
                console.error('[WebSocket] Error:', error);
                this.callbacks.onError?.(error);
            };

            this.ws.onclose = (event) => {
                console.log('[WebSocket] Disconnected', event.code);
                this._stopHeartbeat();
                this.callbacks.onClose?.();

                // 1008 = policy violation (auth failure) — don't retry, token won't fix itself
                if (event.code === 1008) {
                    console.error('[WebSocket] Auth rejected (1008), not reconnecting');
                    return;
                }

                // Reconnect if not intentional close and haven't exceeded max attempts
                if (!this.isIntentionalClose && this.reconnectAttempts < this.maxReconnectAttempts) {
                    this.reconnectAttempts++;
                    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1); // Exponential backoff
                    console.log(`[WebSocket] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
                    this.reconnectTimer = setTimeout(() => {
                        this.connect();
                    }, delay);
                } else if (this.reconnectAttempts >= this.maxReconnectAttempts) {
                    console.error('[WebSocket] Max reconnection attempts reached');
                }
            };
        } catch (err) {
            console.error('[WebSocket] Failed to create connection:', err);
            this.callbacks.onError?.(err as Event);
        }
    }

    private _startHeartbeat(): void {
        this._stopHeartbeat();
        this.pingTimer = setInterval(() => {
            if (this.ws?.readyState !== WebSocket.OPEN) return;
            this.ws.send(JSON.stringify({ type: 'ping' }));
            // If no pong arrives within 10s, treat connection as dead
            this.pongTimer = setTimeout(() => {
                console.warn('[WebSocket] Pong timeout — reconnecting');
                this.ws?.close();
            }, 10_000);
        }, 30_000);
    }

    private _stopHeartbeat(): void {
        if (this.pingTimer) { clearInterval(this.pingTimer); this.pingTimer = null; }
        if (this.pongTimer) { clearTimeout(this.pongTimer); this.pongTimer = null; }
    }

    disconnect(): void {
        this.isIntentionalClose = true;
        this._stopHeartbeat();
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }

    send(message: WebSocketMessage): void {
        if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
        } else {
            console.warn('[WebSocket] Cannot send message, connection not open');
        }
    }

    isConnected(): boolean {
        return this.ws?.readyState === WebSocket.OPEN;
    }
}

/**
 * Helper function to create and connect a WebSocket client
 */
export function connectWebSocket(
    courseId: string,
    callbacks: WebSocketCallbacks
): WebSocketClient {
    const client = new WebSocketClient(courseId, callbacks);
    client.connect();
    return client;
}
