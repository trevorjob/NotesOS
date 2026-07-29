import { api } from '@/lib/api';

// Topic-level resources — the "Read the original" surface: the verbatim uploaded /
// transcribed text behind a synthesized note, before any shaping. Maps to
// GET /api/topics/{topic_id}/resources (list_resources in api/resources.py). The server
// applies the Merge-Agent gate per-viewer: a quarantined resource is only ever returned
// to its own uploader (with quarantined=true), so the client can trust what it receives
// and just badges it "Held · only you".

export interface TopicResource {
  id: string;
  title: string | null;
  content: string;
  file_name: string | null;
  uploader_name: string;
  resource_type: string;
  source_type: string;
  quarantined: boolean;
  needs_review: boolean;
  created_at: string;
}

export interface TopicResourcesPage {
  resources: TopicResource[];
  total: number;
  page: number;
  page_size: number;
}

/** One page of a topic's resources, newest first. */
export async function fetchTopicResources(topicId: string, page = 1): Promise<TopicResourcesPage> {
  const { data } = await api.get(`/api/topics/${topicId}/resources`, { params: { page } });
  return data;
}
