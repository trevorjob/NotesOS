/**
 * NotesOS - WebSocket Client
 * Real-time updates for course resources, fact checks, and grading
 */

import { tokenManager } from './api';

export type WebSocketMessage =
    | { type: 'processing_status'; resource_id: string; status: 'processing' | 'completed' | 'failed' }
    | { type: 'fact_check_complete'; resource_id: string }
    | { type: 'grading:complete'; answer_id: string; attempt_id: string; score: number; encouragement: string }
    | { type: 'resource_created'; data: any }
    | { type: 'resource_updated'; data: any }
    | { type: 'resource_deleted'; resource_id: string }
    | { type: 'user_joined'; user_id: string; timestamp: string | null }
    | { type: 'active_users'; users: string[] }
    | { type: 'echo'; data: any };

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
                this.callbacks.onOpen?.();
            };

            this.ws.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data) as WebSocketMessage;
                    console.log('[WebSocket] Message received:', message.type);
                    this.callbacks.onMessage?.(message);
                } catch (err) {
                    console.error('[WebSocket] Failed to parse message:', err);
                }
            };

            this.ws.onerror = (error) => {
                console.error('[WebSocket] Error:', error);
                this.callbacks.onError?.(error);
            };

            this.ws.onclose = () => {
                console.log('[WebSocket] Disconnected');
                this.callbacks.onClose?.();

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

    disconnect(): void {
        this.isIntentionalClose = true;
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }

    send(message: any): void {
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
