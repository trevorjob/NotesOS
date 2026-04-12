# NotesOS — Gaps & Todos

Gaps found by auditing the actual codebase. Everything here is missing or broken, not hypothetical.

---

## 1. Observability

### 1.1 Logging — Replace `print()` with structured logging

**Problem:** The entire backend uses raw `print()` calls. Only `cache.py` uses Python's `logging` module. There are no log levels, no request context, no correlation IDs, and no way to aggregate or filter logs.

**Files to fix:**
- `backend/app/main.py:21` — prints `settings.DATABASE_URL` on startup (also a security leak)
- `backend/app/services/audio_generator.py` — `print(f"[AUDIO] Script generation failed: {e}")`
- `backend/app/services/fact_checker.py` — multiple `print()` calls
- `backend/app/services/knowledge_synthesizer.py` — `print(f"[KNOWLEDGE] Synthesis failed...")`
- `backend/app/services/notifications.py:66` — `print(f"[NOTIFICATIONS] Failed to push via Redis: {e}")`
- `backend/app/workers/audio_worker.py` — emoji `print()` statements throughout
- `backend/app/workers/chunking_worker.py` — same pattern
- `backend/app/workers/grading_worker.py` — bare `try/except` + prints

**What to do:**
- Set up a shared logger in `backend/app/core/logging.py` — JSON format, configurable log level via env var
- Replace every `print()` with `logger.info/warning/error()`
- Include `worker_name`, `job_id`, `user_id`, `course_id` as structured fields where available
- Never log `DATABASE_URL` or secrets

---

### 1.2 Request/Response Middleware

**Problem:** `main.py` only has CORS and GZip middleware. There is no request logging, no timing, and no correlation IDs.

**What to add in `backend/app/middleware/`:**
- Generate a `X-Request-ID` header on every request (UUID)
- Log: method, path, status code, duration (ms), request ID
- Attach request ID to every log line emitted during that request's lifecycle (via `contextvars`)

---

### 1.3 Health Check — Make it real

**Problem:** `GET /health` returns hardcoded `{"status": "healthy", "database": "connected", "redis": "connected"}`. It does not actually check anything.

**File:** `backend/app/main.py:52-65`

**What to do:**
- Run `SELECT 1` against the database and record latency
- Run `PING` against Redis and record latency
- Check worker queue depths (pending job counts from Redis)
- Return actual status per component with latency
- Return HTTP 503 if any critical dependency is down

---

### 1.4 PostHog — Frontend analytics + error tracking

**Problem:** No analytics, no user event tracking, no error visibility on the frontend.

**PostHog covers:**

- User event tracking (quiz started, resource uploaded, AI chat used, etc.)
- Session replay for debugging UX issues
- Feature flags
- Frontend error capture via `posthog.captureException()`

**What to add:**

- Install `posthog-js` in the frontend
- Initialise in `frontend/src/app/layout.tsx` with `NEXT_PUBLIC_POSTHOG_KEY` and `NEXT_PUBLIC_POSTHOG_HOST`
- Identify users after login: `posthog.identify(user.id, { email, name })`
- Add `NEXT_PUBLIC_POSTHOG_KEY` and `NEXT_PUBLIC_POSTHOG_HOST` to `.env.example`
- Key events to capture at minimum: `quiz_started`, `quiz_submitted`, `resource_uploaded`, `ai_chat_sent`, `topic_viewed`
- For the backend: `posthog-python` SDK to capture server-side events (grading completed, knowledge synthesis done) — keeps event counts accurate regardless of whether the user has the tab open

---

### 1.5 Frontend Error Boundaries

**Problem:** No React Error Boundary exists anywhere in the frontend. An unhandled render error in any component crashes the entire app silently.

**What to add:**
- A global `ErrorBoundary` component wrapping the `(app)` layout
- Per-section boundaries around heavy areas (topic page, quiz, generate-test)
- Display a friendly fallback UI instead of a blank screen
- In the `componentDidCatch` handler, call `posthog.captureException(error)` to route errors through PostHog

---

### 1.6 Worker Monitoring

**Problem:** Workers run with `asyncio.gather()` in `run_workers.py` and report status only via print statements. There is no visibility into queue depth, job failure rates, or stuck jobs.

**What to add:**
- A `GET /api/admin/queue-stats` endpoint returning per-queue: pending count, processing count, failed count, oldest job age
- Proper structured logging per job (start, success, failure with exception)
- A stuck-job definition: jobs in `processing` state for > N minutes get re-queued or flagged
- The `redis_client.py` orphan recovery (lines 168-186) already exists — hook it up to logging so failures surface

---

## 2. Notification System

### 2.1 Notification Types — Expand coverage

**Problem:** Only 4 types exist: `TEST_GRADED`, `AI_SUMMARY_READY`, `INVITE_ACCEPTED`, `GENERAL`. Many actual app events generate no notification.

**File:** `backend/app/models/notification.py:22-27`

**Types to add:**
- `RESOURCE_UPLOADED` — when a classmate uploads a new resource
- `CLASSMATE_JOINED` — when someone joins a course you're in
- `FACT_CHECK_COMPLETE` — separate from AI_SUMMARY_READY
- `QUIZ_REMINDER` — scheduled reminder to review a topic

---

### 2.2 Notification Triggers — Wire up the missing ones

**Problem:** Most app events never create a notification. The grading worker and knowledge worker create them correctly, but resource uploads and classmate joins do not.

**What to wire up:**
- Resource upload → `RESOURCE_UPLOADED` notification to all course members (except uploader)
- Course invite accepted → `INVITE_ACCEPTED` already works, verify it actually fires in `backend/app/api/courses.py`
- Fact-check completion → currently lumped under `AI_SUMMARY_READY`, split it out or confirm it fires correctly from `fact_check_worker`

---

### 2.3 Notification Service — Proper error handling

**Problem:** `backend/app/services/notifications.py:66` catches a Redis publish failure and does `print(f"[NOTIFICATIONS] Failed to push via Redis: {e}")`. The notification is still saved to the DB, but the failure is invisible in production.

**What to fix:**
- Replace `print()` with `logger.error()` including the notification ID and user ID
- Add retry logic: if Redis publish fails, retry once after 1 second before giving up
- The DB record is already created — real-time delivery failure shouldn't be fatal, but it must be logged properly

---

### 2.4 Notification Preferences — Add per-user settings

**Problem:** There is no way for a user to control which notifications they receive. The `preferences` JSONB column on the User model exists but is unused for this.

**What to add:**

**Backend:**
- Add `notification_preferences` to the `User.preferences` JSONB field (or a dedicated column)
- Structure: `{ "TEST_GRADED": true, "AI_SUMMARY_READY": true, "RESOURCE_UPLOADED": true, ... }`
- In `create_and_push_notification()` — check user preference before creating the notification
- `PATCH /api/notifications/preferences` endpoint to update preferences
- `GET /api/notifications/preferences` endpoint to read them

**Frontend:**
- Preferences section in `frontend/src/app/(app)/settings/page.tsx`
- Toggle per notification type (on/off)
- Default all types to `true` on first load

---

### 2.5 Notification UI — Delete and filter

**Problem:** The notification list in settings (`settings/page.tsx:466-503`) has no delete, no filter by type, and no search.

**What to add:**
- Delete individual notification (needs `DELETE /api/notifications/{id}` backend endpoint first)
- Delete all / clear all
- Filter by type (dropdown or tabs: All, Unread, Tests, AI)
- Mark individual as unread (nice to have, lower priority)

**Backend endpoint needed:**
- `DELETE /api/notifications/{notification_id}` — with ownership check (same pattern as the read endpoint at line 90-114)
- `DELETE /api/notifications` — delete all for current user

---

### 2.6 Health Check for WebSocket Connection

**Problem:** `websocket.ts` has reconnection with exponential backoff but no heartbeat. A stale connection that appears open but is actually dead won't be detected until the next message fails.

**What to add:**
- Send a `ping` message from the client every 30 seconds
- Backend WebSocket handler should respond with `pong`
- If no `pong` received within 10 seconds, treat connection as dead and reconnect

---

## 3. AI Chat — One Conversation Per User Per Topic

### 3.1 The Problem

Right now, every time a user sends a message without an active `conversation_id` in state, the backend creates a brand new conversation. There is no unique constraint on `(user_id, topic_id, course_id)` in the database, and the service never checks if one already exists. A page refresh resets the frontend's local `conversationId` state, so the next message spawns yet another conversation. Over time a user ends up with many orphaned conversations for the same topic and loses their history.

**The flaw runs through three layers:**

- **DB** — `ai_conversations` table (`backend/app/models/progress.py:95-120`) has no unique constraint on `(user_id, topic_id)`
- **Backend** — `study_agent._create_conversation()` (`backend/app/services/study_agent.py:108-126`) unconditionally inserts a new row, no lookup first
- **Frontend** — `AIChatPanel.tsx:33-61` loads the "latest" conversation on mount but `conversationId` state starts as `undefined`, so if that effect hasn't resolved yet when the user sends, a new conversation is created

---

### 3.2 What to Fix

**1. Add a unique constraint to the database**

Migration: add a partial unique index on `(user_id, topic_id)` where `topic_id IS NOT NULL`.

```sql
CREATE UNIQUE INDEX uq_ai_conv_user_topic
  ON ai_conversations (user_id, topic_id)
  WHERE topic_id IS NOT NULL;
```

This enforces the rule at the DB level so no code path can accidentally create a duplicate.

**2. Change `_create_conversation` to get-or-create**

In `backend/app/services/study_agent.py`, replace the unconditional insert with a lookup first:

```python
# Look up existing conversation for this user+topic
result = await db.execute(
    select(AIConversation).where(
        AIConversation.user_id == uuid.UUID(user_id),
        AIConversation.topic_id == uuid.UUID(topic_id),
    )
)
existing = result.scalar_one_or_none()
if existing:
    return existing
# else create new
```

**3. Return `conversation_id` from every `/api/study/ask` response**

Already happens (`study_agent.py` returns it), but make sure the frontend always stores it immediately on the first response.

**4. Fix the frontend load sequence in `AIChatPanel.tsx`**

The `loadHistory` effect at lines 33-61 already fetches the existing conversation on mount — but a user can fire a message before that resolves. Fix: disable the send button until the initial load is complete (a simple `isLoading` state guard).

**5. Clean up existing duplicates (one-off migration)**

For each `(user_id, topic_id)` pair with more than one conversation, merge messages into the oldest conversation (by `created_at`) and delete the rest. Run this before applying the unique index.

---

### 3.3 Priority Order Addition

| # | Item | Effort | Impact |
|---|------|--------|--------|
| — | Add unique DB constraint + get-or-create backend logic | Low | High |
| — | AIChatPanel load guard (disable send until history loaded) | Low | High |
| — | One-off migration to collapse duplicate conversations | Low | High |

---

## Priority Order

| # | Item | Effort | Impact |
|---|------|--------|--------|
| 1 | Replace `print()` with structured logging | Low | High |
| 2 | Real health check endpoint | Low | High |
| 3 | Request/response middleware with request IDs | Low | High |
| 4 | PostHog integration (frontend + backend) | Low | High |
| 5 | Frontend Error Boundary (reports to PostHog) | Low | High |
| 6 | Notification service error handling | Low | Medium |
| 7 | Missing notification triggers (resource upload, etc.) | Medium | Medium |
| 8 | `DELETE /api/notifications` endpoints | Low | Medium |
| 9 | Notification preferences (backend + frontend) | Medium | Medium |
| 10 | WebSocket heartbeat/ping | Low | Medium |
| 11 | Notification UI — delete + filter | Medium | Medium |
| 12 | Worker queue monitoring endpoint | Medium | Low |
| 13 | Expand notification types | Low | Low |
