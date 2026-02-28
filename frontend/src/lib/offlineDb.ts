/**
 * NotesOS - Offline Database
 * Typed IndexedDB wrapper using `idb`.
 * All stores are keyed by string IDs; syncQueue / pendingUploads use auto-increment.
 */

'use client';

import { openDB, DBSchema, IDBPDatabase } from 'idb';

// ─── Schema ──────────────────────────────────────────────────────────────────

interface NotesOSDB extends DBSchema {
    courses: {
        key: string;
        value: {
            id: string;
            code: string;
            name: string;
            semester?: string;
            description?: string;
            member_count?: number;
            created_by: string;
            joined_at?: string;
            topics?: unknown[];
            cachedAt: number;
        };
    };

    topics: {
        key: string;
        value: {
            id: string;
            courseId: string;
            title: string;
            description?: string;
            week_number?: number;
            order_index: number;
            mastery_level?: number;
            cachedAt: number;
        };
        indexes: { 'by-course': string };
    };

    resources: {
        key: string;
        value: {
            id: string;
            topicId: string;
            title?: string;
            content: string;
            resource_type: string;
            is_processed: boolean;
            is_verified: boolean;
            uploaded_by: string;
            uploader_name: string;
            created_at: string;
            cachedAt: number;
            [key: string]: unknown;
        };
        indexes: { 'by-topic': string };
    };

    factChecks: {
        key: string;           // resourceId
        value: {
            resourceId: string;
            checks: unknown[];
            cachedAt: number;
        };
    };

    conversations: {
        key: string;
        value: {
            id: string;
            courseId: string;
            title: string | null;
            created_at: string;
            cachedAt: number;
        };
        indexes: { 'by-course': string };
    };

    messages: {
        key: [string, string];  // [conversationId, created_at]
        value: {
            conversationId: string;
            role: 'user' | 'assistant';
            content: string;
            created_at: string;
            sources?: unknown[];
        };
        indexes: { 'by-conversation': string };
    };

    syncQueue: {
        key: number;                 // auto-increment
        value: SyncOperation;
    };

    meta: {
        key: string;
        value: { key: string; value: unknown };
    };
}

export interface SyncOperation {
    id?: number;
    operation: 'create_resource' | 'update_resource' | 'delete_resource';
    payload: unknown;
    timestamp: number;
    retries: number;
}

// ─── DB singleton ─────────────────────────────────────────────────────────────

const DB_NAME = 'notesos-offline';
const DB_VERSION = 1;

let dbPromise: Promise<IDBPDatabase<NotesOSDB>> | null = null;

function getDB(): Promise<IDBPDatabase<NotesOSDB>> {
    if (typeof window === 'undefined') {
        return Promise.reject(new Error('IndexedDB not available (SSR)'));
    }
    if (!dbPromise) {
        dbPromise = openDB<NotesOSDB>(DB_NAME, DB_VERSION, {
            upgrade(db) {
                // courses
                if (!db.objectStoreNames.contains('courses')) {
                    db.createObjectStore('courses', { keyPath: 'id' });
                }

                // topics (indexed by courseId)
                if (!db.objectStoreNames.contains('topics')) {
                    const topicStore = db.createObjectStore('topics', { keyPath: 'id' });
                    topicStore.createIndex('by-course', 'courseId');
                }

                // resources (indexed by topicId)
                if (!db.objectStoreNames.contains('resources')) {
                    const resourceStore = db.createObjectStore('resources', { keyPath: 'id' });
                    resourceStore.createIndex('by-topic', 'topicId');
                }

                // factChecks
                if (!db.objectStoreNames.contains('factChecks')) {
                    db.createObjectStore('factChecks', { keyPath: 'resourceId' });
                }

                // conversations (indexed by courseId)
                if (!db.objectStoreNames.contains('conversations')) {
                    const convStore = db.createObjectStore('conversations', { keyPath: 'id' });
                    convStore.createIndex('by-course', 'courseId');
                }

                // messages (indexed by conversationId)
                if (!db.objectStoreNames.contains('messages')) {
                    const msgStore = db.createObjectStore('messages', { keyPath: ['conversationId', 'created_at'] });
                    msgStore.createIndex('by-conversation', 'conversationId');
                }

                // syncQueue
                if (!db.objectStoreNames.contains('syncQueue')) {
                    db.createObjectStore('syncQueue', { autoIncrement: true, keyPath: 'id' });
                }

                // meta
                if (!db.objectStoreNames.contains('meta')) {
                    db.createObjectStore('meta', { keyPath: 'key' });
                }
            },
        });
    }
    return dbPromise;
}

// ─── Public helpers ───────────────────────────────────────────────────────────

/** Safely run IDB operations; returns null/[] on SSR or error. */
async function safe<T>(fn: () => Promise<T>, fallback: T): Promise<T> {
    try {
        const db = await getDB();
        return await fn.call(null);
    } catch {
        return fallback;
    }
}

export const offlineDb = {
    // ── Courses ──

    async putCourse(course: NotesOSDB['courses']['value']): Promise<void> {
        const db = await getDB();
        await db.put('courses', { ...course, cachedAt: Date.now() });
    },

    async putCourses(courses: Omit<NotesOSDB['courses']['value'], 'cachedAt'>[]): Promise<void> {
        const db = await getDB();
        const tx = db.transaction('courses', 'readwrite');
        await Promise.all([
            ...courses.map(c => tx.store.put({ ...c, cachedAt: Date.now() })),
            tx.done,
        ]);
    },

    async getCourses(): Promise<NotesOSDB['courses']['value'][]> {
        try {
            const db = await getDB();
            return db.getAll('courses');
        } catch {
            return [];
        }
    },

    // ── Topics ──

    async putTopics(courseId: string, topics: unknown[]): Promise<void> {
        const db = await getDB();
        const tx = db.transaction('topics', 'readwrite');
        const typedTopics = topics as Array<{ id: string;[key: string]: unknown }>;
        await Promise.all([
            ...typedTopics.map(t =>
                tx.store.put({ ...(t as NotesOSDB['topics']['value']), courseId, cachedAt: Date.now() })
            ),
            tx.done,
        ]);
    },

    async getTopicsByCourse(courseId: string): Promise<NotesOSDB['topics']['value'][]> {
        try {
            const db = await getDB();
            return db.getAllFromIndex('topics', 'by-course', courseId);
        } catch {
            return [];
        }
    },

    // ── Resources ──

    async putResources(topicId: string, resources: unknown[]): Promise<void> {
        const db = await getDB();
        const tx = db.transaction('resources', 'readwrite');
        const typed = resources as Array<{ id: string;[key: string]: unknown }>;
        await Promise.all([
            ...typed.map(r =>
                tx.store.put({ ...(r as NotesOSDB['resources']['value']), topicId, cachedAt: Date.now() })
            ),
            tx.done,
        ]);
    },

    async getResourcesByTopic(topicId: string): Promise<NotesOSDB['resources']['value'][]> {
        try {
            const db = await getDB();
            return db.getAllFromIndex('resources', 'by-topic', topicId);
        } catch {
            return [];
        }
    },

    async putResource(resource: Omit<NotesOSDB['resources']['value'], 'cachedAt'>): Promise<void> {
        const db = await getDB();
        await db.put('resources', { ...resource, cachedAt: Date.now() });
    },

    async deleteResource(id: string): Promise<void> {
        try {
            const db = await getDB();
            await db.delete('resources', id);
        } catch { /* ignore */ }
    },

    // ── Fact Checks ──

    async putFactChecks(resourceId: string, checks: unknown[]): Promise<void> {
        const db = await getDB();
        await db.put('factChecks', { resourceId, checks, cachedAt: Date.now() });
    },

    async getFactChecks(resourceId: string): Promise<unknown[]> {
        try {
            const db = await getDB();
            const record = await db.get('factChecks', resourceId);
            return record?.checks ?? [];
        } catch {
            return [];
        }
    },

    // ── Conversations ──

    async putConversations(courseId: string, conversations: unknown[]): Promise<void> {
        const db = await getDB();
        const tx = db.transaction('conversations', 'readwrite');
        const typed = conversations as Array<{ id: string;[key: string]: unknown }>;
        await Promise.all([
            ...typed.map(c =>
                tx.store.put({ ...(c as NotesOSDB['conversations']['value']), courseId, cachedAt: Date.now() })
            ),
            tx.done,
        ]);
    },

    async getConversationsByCourse(courseId: string): Promise<NotesOSDB['conversations']['value'][]> {
        try {
            const db = await getDB();
            return db.getAllFromIndex('conversations', 'by-course', courseId);
        } catch {
            return [];
        }
    },

    // ── Messages ──

    async putMessages(conversationId: string, messages: unknown[]): Promise<void> {
        const db = await getDB();
        const tx = db.transaction('messages', 'readwrite');
        const typed = messages as Array<{ role: string; content: string; created_at: string;[key: string]: unknown }>;
        await Promise.all([
            ...typed.map(m =>
                tx.store.put({
                    conversationId,
                    role: m.role as 'user' | 'assistant',
                    content: m.content,
                    created_at: m.created_at || new Date().toISOString(),
                    sources: m.sources as unknown[] | undefined,
                })
            ),
            tx.done,
        ]);
    },

    async getMessages(conversationId: string): Promise<NotesOSDB['messages']['value'][]> {
        try {
            const db = await getDB();
            return db.getAllFromIndex('messages', 'by-conversation', conversationId);
        } catch {
            return [];
        }
    },

    // ── Sync Queue ──

    async enqueueSyncOp(op: Omit<SyncOperation, 'id'>): Promise<void> {
        const db = await getDB();
        await db.add('syncQueue', op);
    },

    async getSyncQueue(): Promise<SyncOperation[]> {
        try {
            const db = await getDB();
            return db.getAll('syncQueue');
        } catch {
            return [];
        }
    },

    async removeSyncOp(id: number): Promise<void> {
        const db = await getDB();
        await db.delete('syncQueue', id);
    },

    // ── Meta ──

    async getMeta(key: string): Promise<unknown> {
        try {
            const db = await getDB();
            const record = await db.get('meta', key);
            return record?.value ?? null;
        } catch {
            return null;
        }
    },

    async setMeta(key: string, value: unknown): Promise<void> {
        const db = await getDB();
        await db.put('meta', { key, value });
    },
};
