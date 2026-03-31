/**
 * Module-level caches for the topic page.
 * Kept in a separate file so they can be imported by both the page
 * and the courses store without Next.js complaining about invalid page exports.
 */

import type { Resource } from '@/components/topic/Sources';

interface TopicDetail {
  id: string;
  title: string;
  description?: string;
  course_id: string;
  knowledge_status?: string;
  audio_status?: string;
  has_audio?: boolean;
}

export const topicDetailCache = new Map<string, TopicDetail>();
export const resourceCache = new Map<string, Resource[]>();
