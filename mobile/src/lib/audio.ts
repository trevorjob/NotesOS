import { api } from '@/lib/api';
import { KnowledgeStatus } from '@/lib/note';

// The Listen surface (docs/listen-audio-plan.md): audio is generalized over a scope, a
// lens (how it's told), and an owner (global/shared vs. personal). The DEFAULT lens is
// always the free shared artifact (one per scope, auto-generated at synthesis); every
// other lens is a personal request the caller pays for later (free today) and which is
// never deduped — each request is a fresh artifact (§1).

export type AudioScopeType = 'course' | 'topic' | 'concept' | 'concept_cluster';
export type AudioLens = 'default' | 'user_instruction' | 'remediation' | 'exam_focused' | 'slower' | 'worked_example';

export interface AudioArtifact {
  id: string | null;
  scope_type: AudioScopeType;
  scope_ref: string;
  knowledge_id: string | null;
  lens: AudioLens;
  owner_id: string | null;
  status: KnowledgeStatus;
  audio_url: string | null;
  duration_seconds: number | null;
  voice: string;
  error_message: string | null;
  stale: boolean;
  audio_suitable: boolean;
  generated_at: string | null;
  updated_at: string | null;
}

export interface FetchAudioOptions {
  lens?: AudioLens;
  owner?: 'global' | 'me';
}

/** The latest artifact for a scope + lens (may be pending/processing/failed). Defaults
 * to the shared global, default-lens artifact when no options are given. */
export async function fetchAudioArtifact(
  scopeType: AudioScopeType,
  scopeRef: string,
  options: FetchAudioOptions = {}
): Promise<AudioArtifact> {
  const { data } = await api.get(`/api/audio/${scopeType}/${scopeRef}`, {
    params: { lens: options.lens, owner: options.owner },
  });
  return data;
}

/** Force regeneration of the shared global artifact (202). Requires knowledge to be synthesized first. */
export async function regenerateAudio(scopeType: AudioScopeType, scopeRef: string): Promise<void> {
  await api.post(`/api/audio/${scopeType}/${scopeRef}/regenerate`);
}

/** Request a personal artifact — a specific lens over a scope, optionally with the
 * caller's own instruction (required for the user_instruction lens, disallowed otherwise).
 * Always creates a fresh artifact; never reuses a prior one for the same lens. */
export async function requestAudio(
  scopeType: AudioScopeType,
  scopeRef: string,
  lens: AudioLens,
  instruction?: string
): Promise<{ artifact_id: string }> {
  const { data } = await api.post('/api/audio/request', {
    scope_type: scopeType,
    scope_ref: scopeRef,
    lens,
    instruction,
  });
  return data;
}

export interface WeakConcept {
  concept_id: string;
  term: string;
  definition: string | null;
}

/** The caller's shakiest concepts within a topic — remediation-suggestion candidates,
 * most-lapsed first. Empty when nothing currently reads as struggling. */
export async function fetchWeakConcepts(topicId: string): Promise<WeakConcept[]> {
  const { data } = await api.get(`/api/topics/${topicId}/weak-concepts`);
  return data.concepts;
}
