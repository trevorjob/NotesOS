import { api } from '@/lib/api';

// Course acquisition — the API surface behind onboarding's cohort→create→invite
// flow and (later) the standalone create screen. Kept here so both callers share
// one typed client instead of hand-rolling axios calls per screen.

export interface CohortCourse {
  course_id: string;
  code: string;
  name: string;
  member_count: number;
  signals: {
    cohort_peers_here: number;
    resource_count: number;
  };
}

export interface ProximityMatch {
  course_id: string;
  code: string;
  name: string;
  member_count: number;
  signals: {
    same_program: number;
    same_entry_year: number;
    classmates_here: number;
  };
}

export interface CreatedCourse {
  id: string;
  code: string;
  name: string;
  invite_code: string | null;
  share_link: string | null;
}

/** Active courses your cohort (same school + program + entry_year) is in that you
 *  aren't. Enrollment-independent — returns results even for a brand-new user. */
export async function fetchCohortCourses(): Promise<CohortCourse[]> {
  const { data } = await api.get('/api/discovery/cohort');
  return data.courses ?? [];
}

// A course the user is actually enrolled in — the "Your courses" list surface.
// Shape mirrors GET /api/courses (list_courses in api/courses.py).
export interface MyCourseTopic {
  id: string;
  title: string;
  order_index: number;
  week_number: number | null;
}

export interface MyCourseLastStudied {
  topic_id: string;
  topic_name: string;
  studied_at: string;
}

export interface MyCourse {
  id: string;
  code: string;
  name: string;
  term_id: string | null;
  term_label: string | null;
  member_count: number;
  created_by: string;
  joined_at: string;
  completion_percentage: number;
  last_studied: MyCourseLastStudied | null;
  topics: MyCourseTopic[];
}

/** Courses the caller is enrolled in, with completion + last-studied data. */
export async function fetchMyCourses(): Promise<MyCourse[]> {
  const { data } = await api.get('/api/courses');
  return data.courses ?? [];
}

export async function joinCourse(params: { courseId?: string; inviteCode?: string }): Promise<void> {
  await api.post('/api/courses/join', {
    course_id: params.courseId,
    invite_code: params.inviteCode,
  });
}

// Create returns one of two shapes: the proximity check offered near-matches
// (nothing created yet), or the course was created. The caller branches on `kind`.
export type CreateCourseResult =
  | { kind: 'created'; course: CreatedCourse }
  | { kind: 'proximity'; matches: ProximityMatch[] };

export async function createCourse(params: {
  code: string;
  name: string;
  force?: boolean;
}): Promise<CreateCourseResult> {
  const { data } = await api.post('/api/courses', {
    code: params.code,
    name: params.name,
    force: params.force ?? false,
  });
  if (data.proximity_check) {
    return { kind: 'proximity', matches: data.matches ?? [] };
  }
  return { kind: 'created', course: data.course };
}
