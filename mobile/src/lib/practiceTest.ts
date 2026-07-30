import { api } from '@/lib/api';
import { AttemptOutcome, Calibration, ChallengePayload, ScheduleState } from '@/lib/retrieval';

// Authored practice tests (B14): a shareable, graded question set built ON the retrieval atom
// and FEEDING it — taking one writes ordinary RetrievalAttempt rows (FSRS / calibration /
// recognition), no separate score store. Mirrors backend/app/api/practice_test.py.

export type AuthoredMode = 'quiz' | 'pretest';
export type PtQuestionType = 'mcq' | 'short_answer' | 'essay';
export type GenerationStatus = 'generating' | 'ready' | 'failed';

export interface TestSummary {
  id: string;
  course_id: string;
  created_by: string;
  title: string;
  mode: AuthoredMode;
  question_type: PtQuestionType;
  scope_topic_ids: string[];
  question_count: number;
  questions_done: number;
  generation_status: GenerationStatus;
  created_at: string;
}

export interface PtQuestion {
  id: string;
  concept_id: string;
  order_index: number;
  prompt: string;
  payload: ChallengePayload;
}

export interface TestDetail extends TestSummary {
  questions: PtQuestion[];
}

export interface PtAnswerResult {
  concept_id: string;
  mode: string;
  outcome: AttemptOutcome;
  state: ScheduleState;
  calibration: Calibration;
}

export interface PtConceptResult {
  concept_id: string;
  concept_text: string;
  grade: string | null;
  score: number | null;
  due: string | null;
}

export interface TestResult {
  test_id: string;
  question_count: number;
  answered_count: number;
  firmed_count: number;
  fading_count: number;
  mean_score: number | null;
  concepts: PtConceptResult[];
}

export interface CreateTestRequest {
  course_id: string;
  title: string;
  mode: AuthoredMode;
  question_type: PtQuestionType;
  question_count: number;
  topic_ids: string[];
}

/** Author a test — returns the shell immediately; questions generate async (poll getTest). */
export async function createTest(body: CreateTestRequest): Promise<TestSummary> {
  const { data } = await api.post('/api/practice-tests', body);
  return data;
}

export async function listTests(courseId: string): Promise<TestSummary[]> {
  const { data } = await api.get('/api/practice-tests', { params: { course_id: courseId } });
  return data;
}

/** A test + its questions (answer key stripped server-side). */
export async function getTest(testId: string): Promise<TestDetail> {
  const { data } = await api.get(`/api/practice-tests/${testId}`);
  return data;
}

export interface AnswerRequest {
  response: unknown;
  predicted_confidence?: number | null;
}

/** Grade one question → records a per-concept attempt (the atom feed). */
export async function answerQuestion(
  testId: string,
  questionId: string,
  body: AnswerRequest,
): Promise<PtAnswerResult> {
  const { data } = await api.post(`/api/practice-tests/${testId}/questions/${questionId}/answer`, body);
  return data;
}

/** The derived run summary — aggregated from the attempt log, never stored. */
export async function getTestResult(testId: string): Promise<TestResult> {
  const { data } = await api.get(`/api/practice-tests/${testId}/result`);
  return data;
}
