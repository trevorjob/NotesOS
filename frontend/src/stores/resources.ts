/**
 * NotesOS - Resources Store
 * Zustand store for resource management
 */

import { create } from 'zustand';
import { api } from '@/lib/api';
import { offlineDb } from '@/lib/offlineDb';

interface ResourceFile {
    id: string;
    file_url: string;
    file_name?: string;
    file_order: number;
    ocr_confidence?: number;
    ocr_provider?: string;
}

interface FactCheck {
    id: string;
    claim: string;
    verdict: 'verified' | 'disputed' | 'unverifiable';
    evidence: string;
    source?: string;
}

interface Resource {
    id: string;
    topic_id: string;
    uploaded_by: string;
    uploader_name: string;
    title?: string;
    content: string;
    resource_type: string;
    file_url?: string;
    file_name?: string;
    source_type: string;
    is_processed: boolean;
    ocr_cleaned: boolean;
    is_verified: boolean;
    ocr_confidence?: number;
    ocr_provider?: string;
    files: ResourceFile[];
    created_at: string;
    updated_at: string;
    processing_status?: 'processing' | 'completed' | 'failed'; // For WebSocket updates
}

interface ResourcesState {
    resources: Resource[];
    currentTopicId: string | null;
    isLoading: boolean;
    _isFetchingResources: boolean;
    isUploading: boolean;
    uploadProgress: number;
    error: string | null;
    total: number;
    page: number;
    pageSize: number;
    factChecks: Record<string, FactCheck[]>; // resourceId -> fact checks
    isLoadingFactChecks: Record<string, boolean>;

    // Actions
    fetchResources: (topicId: string, page?: number) => Promise<void>;
    createTextResource: (topicId: string, data: { title?: string; content: string }) => Promise<void>;
    uploadFiles: (topicId: string, courseId: string, files: File[], title?: string, isHandwritten?: boolean) => Promise<void>;
    deleteResource: (resourceId: string) => Promise<void>;
    factCheckResource: (resourceId: string) => Promise<void>;
    fetchFactChecks: (resourceId: string) => Promise<void>;
    updateResourceProcessingStatus: (resourceId: string, status: 'processing' | 'completed' | 'failed') => void;
    updateResource: (resourceId: string, data: Partial<{ title: string; description: string }>) => Promise<void>;
    retranscribeResource: (resourceId: string) => Promise<void>;
    clearError: () => void;
}

export const useResourcesStore = create<ResourcesState>()((set, get) => ({
    resources: [],
    currentTopicId: null,
    isLoading: false,
    _isFetchingResources: false,
    isUploading: false,
    uploadProgress: 0,
    error: null,
    total: 0,
    page: 1,
    pageSize: 20,
    factChecks: {},
    isLoadingFactChecks: {},

    fetchResources: async (topicId: string, page = 1) => {
        // Dedup parallel/StrictMode double-invoke calls for the same topic+page
        const state = get();
        if (state._isFetchingResources && state.currentTopicId === topicId) return;

        set({ isLoading: true, error: null, currentTopicId: topicId, _isFetchingResources: true });

        // Offline: serve from IndexedDB (only page 1; cached data isn't paginated)
        if (typeof navigator !== 'undefined' && !navigator.onLine) {
            const cached = await offlineDb.getResourcesByTopic(topicId);
            set({ resources: cached as unknown as Resource[], total: cached.length, page: 1, isLoading: false, _isFetchingResources: false });
            return;
        }

        try {
            const response = await api.resources.getByTopic(topicId, page, get().pageSize);
            const resources = response.data.resources || [];
            set({
                resources,
                total: response.data.total || 0,
                page: response.data.page || 1,
                isLoading: false,
                _isFetchingResources: false,
            });
            if (page === 1 && resources.length > 0) {
                offlineDb.putResources(topicId, resources).catch(() => { });
            }
        } catch (error) {
            const cached = await offlineDb.getResourcesByTopic(topicId);
            if (cached.length > 0) {
                set({ resources: cached as unknown as Resource[], total: cached.length, page: 1, isLoading: false, _isFetchingResources: false });
            } else {
                const errorMessage = (error as Error & { response?: { data?: { detail?: string } } }).response?.data?.detail || 'Failed to fetch resources';
                set({ isLoading: false, error: errorMessage, _isFetchingResources: false });
            }
        }
    },

    createTextResource: async (topicId: string, data: { title?: string; content: string }) => {
        set({ error: null });
        try {
            await api.resources.createText(topicId, data);

            // Refresh resources list
            await get().fetchResources(topicId);
        } catch (error) {
            const errorMessage =
                (error as Error & { response?: { data?: { detail?: string } } }).response?.data?.detail || 'Failed to create resource';
            set({ error: errorMessage });
            throw new Error(errorMessage);
        }
    },

    uploadFiles: async (topicId: string, courseId: string, files: File[], title?: string, isHandwritten?: boolean) => {
        set({ isUploading: true, uploadProgress: 0, error: null });
        try {
            await api.resources.upload(
                topicId,
                courseId,
                files,
                title,
                isHandwritten,
                (percent: number) => set({ uploadProgress: percent }),
            );

            set({ uploadProgress: 100, isUploading: false });

            // Refresh resources list
            await get().fetchResources(topicId);
        } catch (error) {
            const errorMessage =
                (error as Error & { response?: { data?: { detail?: string } } }).response?.data?.detail || (error as Error).message || 'Failed to upload files';
            set({ isUploading: false, uploadProgress: 0, error: errorMessage });
            throw new Error(errorMessage);
        }
    },

    deleteResource: async (resourceId: string) => {
        set({ error: null });
        try {
            await api.resources.delete(resourceId);

            // Evict from IDB cache
            offlineDb.deleteResource(resourceId).catch(() => { });

            // Refresh current topic's resources
            const { currentTopicId } = get();
            if (currentTopicId) {
                await get().fetchResources(currentTopicId);
            }
        } catch (error) {
            const errorMessage =
                (error as Error & { response?: { data?: { detail?: string } } }).response?.data?.detail || 'Failed to delete resource';
            set({ error: errorMessage });
            throw new Error(errorMessage);
        }
    },

    factCheckResource: async (resourceId: string) => {
        set({ error: null });
        try {
            await api.ai.verifyResource(resourceId);
            // Fact checking is async, will update via websocket (fact_check_complete event)
            // No need for setTimeout polling - WebSocket will notify us
        } catch (error) {
            const errorMessage =
                (error as Error & { response?: { data?: { detail?: string } } }).response?.data?.detail || 'Failed to start fact check';
            set({ error: errorMessage });
            throw new Error(errorMessage);
        }
    },

    fetchFactChecks: async (resourceId: string) => {
        set((state) => ({
            isLoadingFactChecks: { ...state.isLoadingFactChecks, [resourceId]: true },
            error: null,
        }));

        // Offline: serve from IndexedDB
        if (typeof navigator !== 'undefined' && !navigator.onLine) {
            const cached = await offlineDb.getFactChecks(resourceId);
            set((state) => ({
                factChecks: { ...state.factChecks, [resourceId]: cached as FactCheck[] },
                isLoadingFactChecks: { ...state.isLoadingFactChecks, [resourceId]: false },
            }));
            return;
        }

        try {
            const response = await api.ai.getFactChecks(resourceId);
            const checks = response.data || [];
            set((state) => ({
                factChecks: { ...state.factChecks, [resourceId]: checks },
                isLoadingFactChecks: { ...state.isLoadingFactChecks, [resourceId]: false },
            }));
            // Write-through to IDB
            if (checks.length > 0) {
                offlineDb.putFactChecks(resourceId, checks).catch(() => { });
            }
        } catch {
            // Network error — try IDB cache
            const cached = await offlineDb.getFactChecks(resourceId);
            set((state) => ({
                factChecks: { ...state.factChecks, [resourceId]: cached as FactCheck[] },
                isLoadingFactChecks: { ...state.isLoadingFactChecks, [resourceId]: false },
            }));
        }
    },

    updateResourceProcessingStatus: (resourceId: string, status: 'processing' | 'completed' | 'failed') => {
        set((state) => ({
            resources: state.resources.map((r) =>
                r.id === resourceId
                    ? {
                        ...r,
                        is_processed: status === 'completed' ? true : r.is_processed,
                        processing_status: status,
                    }
                    : r
            ),
        }));
    },

    updateResource: async (resourceId: string, data: Partial<{ title: string; description: string }>) => {
        set({ error: null });
        try {
            await api.resources.update(resourceId, data);
            const { currentTopicId } = get();
            if (currentTopicId) {
                await get().fetchResources(currentTopicId);
            }
        } catch (error) {
            const errorMessage =
                (error as Error & { response?: { data?: { detail?: string } } }).response?.data?.detail || 'Failed to update resource';
            set({ error: errorMessage });
            throw new Error(errorMessage);
        }
    },

    retranscribeResource: async (resourceId: string) => {
        set({ error: null });
        try {
            await api.resources.retranscribe(resourceId);
            // Optimistically mark as processing
            set((state) => ({
                resources: state.resources.map((r) =>
                    r.id === resourceId
                        ? { ...r, processing_status: 'processing', is_processed: false }
                        : r
                ),
            }));
        } catch (error) {
            const errorMessage =
                (error as Error & { response?: { data?: { detail?: string } } }).response?.data?.detail || 'Failed to re-transcribe resource';
            set({ error: errorMessage });
            throw new Error(errorMessage);
        }
    },

    clearError: () => set({ error: null }),
}));
