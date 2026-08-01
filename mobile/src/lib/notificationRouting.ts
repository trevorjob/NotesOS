import type { Href } from 'expo-router';
import type { NotificationItem, NotificationType } from '@/lib/notifications';

// Where a notification's meta_data sends the user, on tap — shared by the in-app feed
// (notifications.tsx) and the OS push tap handler (lib/push.ts), so both lanes land
// identically. Keys mirror exactly what each backend emitter stamps (see
// notifications-plan.md §4): CLASSMATE_JOINED/RESOURCE_UPLOADED/AI_SUMMARY_READY carry
// course_id (+ topic_id where relevant); DECAY_NUDGE carries topic_id + course_id but no
// resolved concept term/state, so it lands on the note rather than guessing a /retrieval
// deep link; recognition (GENERAL, kind="recognition") carries no course/topic at all.

function asString(value: unknown): string | undefined {
  return typeof value === 'string' && value.length > 0 ? value : undefined;
}

export function routeForNotification(item: Pick<NotificationItem, 'type' | 'meta_data'>): Href | null {
  const meta = item.meta_data ?? {};
  const topicId = asString(meta.topic_id);
  const courseId = asString(meta.course_id);
  const type = item.type as NotificationType;

  switch (type) {
    case 'DECAY_NUDGE':
    case 'AI_SUMMARY_READY':
      if (topicId) return { pathname: '/note', params: { topicId, courseId } };
      return courseId ? { pathname: '/topics', params: { courseId } } : null;
    case 'RESOURCE_UPLOADED':
      if (topicId) return { pathname: '/note', params: { topicId, courseId } };
      return courseId ? { pathname: '/topics', params: { courseId } } : null;
    case 'CLASSMATE_JOINED':
      return courseId ? { pathname: '/topics', params: { courseId } } : null;
    default:
      return null; // GENERAL (incl. recognition) and unknown types: stay on the feed.
  }
}
