import { api } from '@/lib/api';

// Discovery client — the "Discover" screen. Two live surfaces, both pull-only
// (they surface courses/people; joining is the separate POST /api/courses/join):
//   • courses to join — classmate-overlap (/discovery/courses) merged with cohort
//     (/discovery/cohort) so a brand-new user with no enrollments still sees results.
//   • classmates — people you already share a course with (/discovery/classmates).

export interface Classmate {
  id: string;
  full_name: string | null;
  avatar_url: string | null;
  shared_courses: number;
}

export interface DiscoverCourse {
  course_id: string;
  code: string;
  name: string;
  member_count: number;
  // Which signal is present depends on the source (classmate vs. cohort); both
  // carry resource_count. `courseReason` turns these into a human line.
  signals: {
    classmates_here?: number;
    cohort_peers_here?: number;
    resource_count: number;
  };
}

export async function fetchClassmates(): Promise<Classmate[]> {
  const { data } = await api.get('/api/discovery/classmates');
  return data.classmates ?? [];
}

/** Courses to join: classmate-overlap first (strongest signal), then cohort
 *  courses the classmate surface didn't already include, deduped by course id. */
export async function fetchDiscoverCourses(): Promise<DiscoverCourse[]> {
  const [classmate, cohort] = await Promise.all([
    api.get('/api/discovery/courses').then((r) => (r.data.courses ?? []) as DiscoverCourse[]),
    api.get('/api/discovery/cohort').then((r) => (r.data.courses ?? []) as DiscoverCourse[]),
  ]);

  const byId = new Map<string, DiscoverCourse>();
  for (const course of classmate) byId.set(course.course_id, course);
  for (const course of cohort) {
    if (!byId.has(course.course_id)) byId.set(course.course_id, course);
  }
  return [...byId.values()];
}

/** One-line reason a course is surfaced, strongest signal first. */
export function courseReason(course: DiscoverCourse): string {
  const classmates = course.signals.classmates_here ?? 0;
  if (classmates > 0) {
    return `${classmates} classmate${classmates === 1 ? '' : 's'} joined`;
  }
  const peers = course.signals.cohort_peers_here ?? 0;
  if (peers > 0) {
    return `${peers} in your year joined`;
  }
  return 'Active at your school';
}
