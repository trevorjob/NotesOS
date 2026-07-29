import { api } from '@/lib/api';

// The note surface (§2.6): the consolidated note is the shared, shaped study layer;
// the per-concept mastery is the caller's own — two separate calls because the note is
// cacheable across a course while mastery is per-user and live (see api/knowledge.py).

export type MasteryState = 'new' | 'solid' | 'fading' | 'shaky';
export type KnowledgeStatus = 'pending' | 'processing' | 'completed' | 'failed';

export interface NoteConcept {
  term: string;
  definition: string | null;
}

export interface TopicKnowledge {
  id: string | null;
  topic_id: string;
  status: KnowledgeStatus;
  consolidated_note: string | null;
  key_points: string[];
  concepts: NoteConcept[];
  source_count: number;
  error_message: string | null;
  generated_at: string | null;
  updated_at: string | null;
}

export interface ConceptMastery {
  concept_id: string;
  term: string;
  definition: string | null;
  state: MasteryState;
  due: string | null;
  reps: number;
  lapses: number;
}

export interface ConceptStates {
  topic_id: string;
  concepts: ConceptMastery[];
  summary: Record<MasteryState, number>;
}

export interface TopicHeader {
  id: string;
  course_id: string;
  title: string;
  description: string | null;
  week_number: number | null;
  knowledge_status: KnowledgeStatus;
  has_audio: boolean;
}

/** Topic header (title + course) — the note's own H1, independent of its callers. */
export async function fetchTopicHeader(topicId: string): Promise<TopicHeader> {
  const { data } = await api.get(`/api/topics/${topicId}`);
  return data;
}

/** The shared consolidated note for a topic (may be pending/processing/failed). */
export async function fetchTopicKnowledge(topicId: string): Promise<TopicKnowledge> {
  const { data } = await api.get(`/api/topics/${topicId}/knowledge`);
  return data;
}

/** The caller's per-concept mastery over the topic — the note's heat-map. */
export async function fetchConceptStates(topicId: string): Promise<ConceptStates> {
  const { data } = await api.get(`/api/topics/${topicId}/concept-states`);
  return data;
}

/** Force a full re-synthesis of the note (202). Used to recover a failed note. */
export async function regenerateKnowledge(topicId: string): Promise<void> {
  await api.post(`/api/topics/${topicId}/knowledge/regenerate`);
}

export interface Contributor {
  id: string;
  name: string;
}

export interface RecentContribution {
  resource_id: string;
  title: string;
  uploader_name: string;
  created_at: string;
}

export interface TopicContributions {
  topic_id: string;
  contributors: Contributor[];
  contributor_count: number;
  recent: RecentContribution[];
  new_since_last_read: number | null;
}

/** The note's attribution layer — who built it, recent additions, new-since-last-read. */
export async function fetchTopicContributions(topicId: string): Promise<TopicContributions> {
  const { data } = await api.get(`/api/topics/${topicId}/contributions`);
  return data;
}
