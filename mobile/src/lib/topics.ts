import { api } from '@/lib/api';

// Course-detail client — the topics screen. GET /api/courses/{id} returns the course
// header (name/code) plus its topics in one enrollment-checked call, so the screen
// needs a single request. Per-topic synthesis status / resource counts live only on
// GET /api/topics/{id} (deliberately not embedded in the list to avoid an N+1) and are
// surfaced on the note screen, not here.

export interface CourseTopic {
  id: string;
  title: string;
  description: string | null;
  week_number: number | null;
  order_index: number;
}

export interface CourseDetail {
  id: string;
  code: string;
  name: string;
  description: string | null;
  school_id: string | null;
}

export interface CourseWithTopics {
  course: CourseDetail;
  topics: CourseTopic[];
}

/** The course header + its topics (ordered by order_index server-side). */
export async function fetchCourseTopics(courseId: string): Promise<CourseWithTopics> {
  const { data } = await api.get(`/api/courses/${courseId}`);
  return { course: data.course, topics: data.topics ?? [] };
}
