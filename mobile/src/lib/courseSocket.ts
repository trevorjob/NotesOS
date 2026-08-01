import { getAccessToken } from '@/lib/auth';
import { ReconnectingSocket, SocketCallbacks, WS_BASE_URL } from '@/lib/wsClient';

// Course-room WebSocket client: WS /ws/{course_id}?token=…. Built for capture's live
// progress; also the room other course-scoped broadcasts (resource_created, etc.) land on.
// Mirrors frontend/src/lib/websocket.ts, trimmed to what capture needs.

export type CourseSocketCallbacks = SocketCallbacks;

export class CourseSocket extends ReconnectingSocket {
  private readonly courseId: string;

  constructor(courseId: string, callbacks: CourseSocketCallbacks) {
    super(callbacks);
    this.courseId = courseId;
  }

  protected async buildUrl(): Promise<string | null> {
    const token = await getAccessToken();
    if (!token) return null;
    return `${WS_BASE_URL}/ws/${this.courseId}?token=${encodeURIComponent(token)}`;
  }
}
