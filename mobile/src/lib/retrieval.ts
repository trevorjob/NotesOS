import { File } from 'expo-file-system';
import { api, API_BASE_URL } from '@/lib/api';
import { getAccessToken } from '@/lib/auth';

// The retrieval engine (§2.7 / system-spec §5): a session is TWO requests — POST /next
// picks a concept + has a mode generate a challenge (answer key held server-side under an
// opaque challenge_id), POST /attempt evaluates the response, records it (the ONLY writer
// of ConceptState), advances the FSRS schedule, and returns calibration (predicted vs
// actual). Recap/dump are the free-recall siblings: topic-scoped, one response graded
// across many concepts. Mirrors backend/app/api/retrieval.py.

export type QuestionType = 'mcq' | 'short_answer' | 'essay' | 'worked' | 'numeric';

// The self-grade vocabulary a worked (STEM) problem accepts — 1:1 with FSRS grades.
export type SelfGrade = 'again' | 'hard' | 'good' | 'easy';

export interface ModeInfo {
  key: string;
  affinity: number;
}

export interface ChallengePayload {
  question_type?: QuestionType;
  answer_options?: string[] | null;
  [key: string]: unknown;
}

export interface NextChallenge {
  challenge_id: string;
  concept_id: string;
  concept_text: string;
  mode: string;
  prompt: string;
  payload: ChallengePayload;
  // teach / ramble are a back-and-forth: drive /turn (not /attempt). The opening prompt is
  // the first AI turn; capture predicted confidence before the first spoken turn.
  conversational?: boolean;
}

export type CalibrationLabel = 'underconfident' | 'overconfident' | 'calibrated';

export interface Calibration {
  predicted: number | null;
  actual: number;
  delta: number | null;
  label: CalibrationLabel | null;
}

export interface AttemptOutcome {
  score: number;
  grade: string;
  feedback: string | null;
  detail: Record<string, unknown>;
}

export interface ScheduleState {
  due: string | null;
  reps: number;
  lapses: number;
  stability: number | null;
  difficulty: number | null;
  last_grade: string | null;
}

export interface AttemptResult {
  concept_id: string;
  mode: string;
  outcome: AttemptOutcome;
  state: ScheduleState;
  calibration: Calibration;
}

export interface RevealResult {
  question_type: string;
  worked_solution: string | null;
}

export interface FreeRecallChallenge {
  challenge_id: string;
  topic_id: string;
  topic_title: string;
  prompt: string;
  concept_count: number;
}

export interface RecapConceptOutcome {
  concept_id: string;
  concept_text: string;
  score: number;
  grade: string;
  feedback: string | null;
  covered: string[];
  missed: string[];
  due: string | null;
}

export interface FreeRecallResult {
  mode: string;
  topic_id: string;
  concept_count: number;
  mean_score: number;
  outcomes: RecapConceptOutcome[];
}

/** Available modes + how strongly each suits a subject family (the mode-mix knob). */
export async function fetchModes(family?: string): Promise<ModeInfo[]> {
  const { data } = await api.get('/api/retrieval/modes', {
    params: family ? { family } : undefined,
  });
  return data;
}

// A topic's subject profile: its family + the rendering / grading / mode-affinity it drives.
// mode_mix keys are the engine's mode ids (note: brain dump is "brain_dump"), value = affinity
// 0..1 — the knob that makes the mode picker context-worthy (best-fit first).
export interface TopicProfile {
  topic_id: string;
  subject_family: 'STEM' | 'LANGUAGE' | 'HUMANITIES' | 'SOCIAL_SCIENCE' | 'GENERAL';
  overridden: boolean;
  render: string;
  grading: string;
  mode_mix: Record<string, number>;
}

export async function fetchTopicProfile(topicId: string): Promise<TopicProfile> {
  const { data } = await api.get(`/api/retrieval/topics/${topicId}/profile`);
  return data;
}

// The engine's "single highest-value thing to study now" — the home doorway (system-spec
// §5/§8). kind cascades review → calibration → dump → new → get_ahead; null when the user
// has no concepts yet (the client sends them to capture instead of an empty study surface).
export interface NextAction {
  kind: 'review' | 'calibration' | 'dump' | 'new' | 'get_ahead';
  course_id: string;
  topic_id: string;
  topic_title: string;
  concept_ids: string[];
  mode: string;
  reason: string;
  est_minutes: number;
}

export async function fetchNextAction(params?: { course_id?: string; topic_id?: string }): Promise<NextAction | null> {
  const { data } = await api.get('/api/retrieval/next-action', { params });
  return data ?? null;
}

// The warm close (system-spec §6): what the most recent session changed — firmed vs.
// still-slipping concepts + the calibration delta. null when there's no session yet.
export interface SessionSummaryConcept {
  concept_id: string;
  concept_text: string;
  state: 'solid' | 'fading' | 'shaky';
  attempts: number;
  mean_score: number;
}

export interface SessionSummary {
  started_at: string;
  ended_at: string;
  attempt_count: number;
  concept_count: number;
  firmed: SessionSummaryConcept[];
  slipping: SessionSummaryConcept[];
  calibration_delta: number | null;
  calibration_label: CalibrationLabel | null;
  predicted_count: number;
}

export async function fetchSessionSummary(params?: { course_id?: string; topic_id?: string }): Promise<SessionSummary | null> {
  const { data } = await api.get('/api/retrieval/session-summary', { params });
  return data ?? null;
}

export interface NextRequest {
  mode: string;
  scope?: string;
  topic_id?: string;
  course_id?: string;
  concept_id?: string;
}

/** Pick a concept and have the mode pose a challenge (answer key stays server-side). */
export async function nextChallenge(body: NextRequest): Promise<NextChallenge> {
  const { data } = await api.post('/api/retrieval/next', body);
  return data;
}

export interface AttemptRequest {
  challenge_id: string;
  response: unknown;
  predicted_confidence?: number | null;
  answer_origin?: 'paper';
}

/** Evaluate + record the response; returns outcome, new schedule, calibration. */
export async function submitAttempt(body: AttemptRequest): Promise<AttemptResult> {
  const { data } = await api.post('/api/retrieval/attempt', body);
  return data;
}

// A conversational bout (teach / ramble): each /turn either digs (AI ``reply``, keep going)
// or closes — at which point the single graded attempt lands here, exactly like /attempt.
// Predicted confidence is stamped on the first turn (captured at open, before talking).
export interface TurnRequest {
  challenge_id: string;
  message: string;
  predicted_confidence?: number | null;
  end?: boolean;
}

export interface ConversationTurnResult {
  challenge_id: string;
  closed: boolean;
  turn_count: number;
  reply: string | null;
  close_reason: string | null;
  concept_id: string | null;
  mode: string | null;
  outcome: AttemptOutcome | null;
  state: ScheduleState | null;
  calibration: Calibration | null;
}

/** Advance a conversational bout — dig one turn, or grade and close. */
export async function submitTurn(body: TurnRequest): Promise<ConversationTurnResult> {
  const { data } = await api.post('/api/retrieval/turn', body);
  return data;
}

/** Stamp the confidence prediction, then reveal a worked problem's solution (B9). */
export async function revealSolution(
  challengeId: string,
  predictedConfidence?: number | null,
): Promise<RevealResult> {
  const { data } = await api.post('/api/retrieval/reveal', {
    challenge_id: challengeId,
    predicted_confidence: predictedConfidence ?? null,
  });
  return data;
}

/** Open a recap of the last session in a topic (404 when nothing to recap). */
export async function recapNext(topicId: string): Promise<FreeRecallChallenge> {
  const { data } = await api.post('/api/retrieval/recap/next', { topic_id: topicId });
  return data;
}

export async function recapAttempt(body: AttemptRequest): Promise<FreeRecallResult> {
  const { data } = await api.post('/api/retrieval/recap/attempt', body);
  return data;
}

/** Open a brain dump over the whole topic (409 when the topic has no concepts yet). */
export async function dumpNext(topicId: string): Promise<FreeRecallChallenge> {
  const { data } = await api.post('/api/retrieval/dump/next', { topic_id: topicId });
  return data;
}

export async function dumpAttempt(body: AttemptRequest): Promise<FreeRecallResult> {
  const { data } = await api.post('/api/retrieval/dump/attempt', body);
  return data;
}

// Paper substrate (B8): photo(s) of handwriting → transcription for the user to confirm or
// correct, then submitted as text through the normal /attempt flow with answer_origin:"paper".
// Photos are ephemeral (never stored). Uses fetch (+ manual JWT) because the endpoint is
// multipart and SDK-57's winter FormData needs Blob-compatible expo File parts, not axios.
export interface TranscribeResult {
  transcription: string;
  requires_confirmation: true;
  page_count: number;
  has_uncertain: boolean;
  has_illegible: boolean;
}

export async function transcribePaper(files: { uri: string }[]): Promise<TranscribeResult> {
  const form = new FormData();
  for (const f of files) {
    form.append('files', new File(f.uri));
  }
  const token = await getAccessToken();
  const res = await fetch(`${API_BASE_URL}/api/retrieval/transcribe`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body: form,
  });
  if (!res.ok) {
    let detail = `Couldn’t read that photo (${res.status}). Try another shot.`;
    try {
      const body = await res.json();
      if (typeof body?.detail === 'string') detail = body.detail;
    } catch {
      // non-JSON error body — keep the default message
    }
    throw new Error(detail);
  }
  return res.json();
}
