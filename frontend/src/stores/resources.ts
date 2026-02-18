/**
 * NotesOS - Resources Store
 * Zustand store for resource management
 */

import { create } from 'zustand';
import { api } from '@/lib/api';

interface ResourceFile {
    id: string;
    file_url: string;
    file_name?: string;
    file_order: number;
    ocr_confidence?: number;
    ocr_provider?: string;
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
}

interface ResourcesState {
    resources: Resource[];
    currentTopicId: string | null;
    isLoading: boolean;
    isUploading: boolean;
    uploadProgress: number;
    error: string | null;
    total: number;
    page: number;
    pageSize: number;
    factChecks: Record<string, any[]>; // resourceId -> fact checks
    isLoadingFactChecks: Record<string, boolean>;

    // Actions
    fetchResources: (topicId: string, page?: number) => Promise<void>;
    createTextResource: (topicId: string, data: { title?: string; content: string }) => Promise<void>;
    uploadFiles: (topicId: string, courseId: string, files: File[], title?: string, isHandwritten?: boolean) => Promise<void>;
    deleteResource: (resourceId: string) => Promise<void>;
    factCheckResource: (resourceId: string) => Promise<void>;
    fetchFactChecks: (resourceId: string) => Promise<void>;
    clearError: () => void;
}

export const useResourcesStore = create<ResourcesState>()((set, get) => ({
    resources: [],
    currentTopicId: null,
    isLoading: false,
    isUploading: false,
    uploadProgress: 0,
    error: null,
    total: 0,
    page: 1,
    pageSize: 20,
    factChecks: {},
    isLoadingFactChecks: {},

    fetchResources: async (topicId: string, page = 1) => {
        set({ isLoading: true, error: null, currentTopicId: topicId });
        try {
            const response = await api.resources.getByTopic(topicId, page, get().pageSize);
            set({
                resources: response.data.resources || [],
                total: response.data.total || 0,
                page: response.data.page || 1,
                isLoading: false,
            });
        } catch (error: any) {
            const errorMessage =
                error.response?.data?.detail || 'Failed to fetch resources';
            set({ isLoading: false, error: errorMessage });
        }
    },

    createTextResource: async (topicId: string, data: { title?: string; content: string }) => {
        set({ error: null });
        try {
            await api.resources.createText(topicId, data);

            // Refresh resources list
            await get().fetchResources(topicId);
        } catch (error: any) {
            const errorMessage =
                error.response?.data?.detail || 'Failed to create resource';
            set({ error: errorMessage });
            throw new Error(errorMessage);
        }
    },

    uploadFiles: async (topicId: string, courseId: string, files: File[], title?: string, isHandwritten?: boolean) => {
        set({ isUploading: true, uploadProgress: 0, error: null });
        try {
            // Simulated progress (real progress would need onUploadProgress)
            const progressInterval = setInterval(() => {
                set(state => ({
                    uploadProgress: Math.min(state.uploadProgress + 10, 90),
                }));
            }, 200);

            await api.resources.upload(topicId, courseId, files, title, isHandwritten);

            clearInterval(progressInterval);
            set({ uploadProgress: 100, isUploading: false });

            // Refresh resources list
            await get().fetchResources(topicId);
        } catch (error: any) {
            const errorMessage =
                error.response?.data?.detail || 'Failed to upload files';
            set({ isUploading: false, uploadProgress: 0, error: errorMessage });
            throw new Error(errorMessage);
        }
    },

    deleteResource: async (resourceId: string) => {
        set({ error: null });
        try {
            await api.resources.delete(resourceId);

            // Refresh current topic's resources
            const { currentTopicId } = get();
            if (currentTopicId) {
                await get().fetchResources(currentTopicId);
            }
        } catch (error: any) {
            const errorMessage =
                error.response?.data?.detail || 'Failed to delete resource';
            set({ error: errorMessage });
            throw new Error(errorMessage);
        }
    },

    factCheckResource: async (resourceId: string) => {
        set({ error: null });
        try {
            await api.ai.verifyResource(resourceId);
            // Note: Fact checking is async, will update via websocket or polling
            // Fetch results immediately (they may become available)
            setTimeout(() => get().fetchFactChecks(resourceId), 2000);
        } catch (error: any) {
            const errorMessage =
                error.response?.data?.detail || 'Failed to start fact check';
            set({ error: errorMessage });
            throw new Error(errorMessage);
        }
    },

    fetchFactChecks: async (resourceId: string) => {
        set((state) => ({
            isLoadingFactChecks: { ...state.isLoadingFactChecks, [resourceId]: true },
            error: null,
        }));
        try {
            const response = await api.ai.getFactChecks(resourceId);
            set((state) => ({
                factChecks: { ...state.factChecks, [resourceId]: response.data },
                isLoadingFactChecks: { ...state.isLoadingFactChecks, [resourceId]: false },
            }));
        } catch (error: any) {
            set((state) => ({
                isLoadingFactChecks: { ...state.isLoadingFactChecks, [resourceId]: false },
            }));
            // Silently fail - fact checks may not exist yet
        }
    },

    clearError: () => set({ error: null }),
}));
