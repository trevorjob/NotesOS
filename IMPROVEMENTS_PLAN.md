# NotesOS — Improvement Plan

**Scope:** Backend optimization, offline mode (per spec), UI/UX overhaul, and multimodal AI for resources.  
**Out of scope (for now):** Deployment configs (nginx, systemd, deploy.sh).

---

## 1. Backend optimization

**Goals:** Reduce latency, lower DB load, and make expensive operations cacheable where safe.

### 1.1 Cache layer (Redis)

| What | Approach |
|------|----------|
| **Read-through cache** | Cache GET responses for **idempotent, user-agnostic or user-scoped** endpoints. Use short TTLs where data can change (e.g. course list, topic list). |
| **Cache keys** | `notesos:v1:{endpoint}:{scope}:{id}` e.g. `notesos:v1:course:user:abc:list`, `notesos:v1:topic:xyz`. Include user/course in key where response is user-specific. |
| **TTLs** | Course/topic list: 60–120s. Single resource/topic: 30–60s. Static-ish (e.g. research once generated): 5–15 min. |
| **Invalidation** | On write (create/update/delete): invalidate related keys (e.g. on topic create, invalidate course’s topic list and course list for that user). Use Redis DEL or a small “version” suffix in the key bumped on write. |
| **What to cache first** | `GET /api/courses`, `GET /api/courses/{id}` (with topics), `GET /api/courses/{id}/topics`, `GET /api/topics/{id}`. For **resources by topic** use a cached key only if that list is paginated (see 1.2). Skip auth and mutating endpoints. |

**Implementation sketch:**

- Add a small **cache module** (e.g. `app/services/cache.py`) with `get(key)`, `set(key, value, ttl_sec)`, `delete(key)`, `delete_pattern(prefix)`.
- Optional **middleware or per-route decorator** for “cache this response” (e.g. `@cache_response(ttl=60, key_builder=...)`).
- Invalidate in existing routes: after create/update/delete in courses, topics, resources, progress (where applicable).

### 1.2 Request handling and pagination

**Pagination — only where it makes sense:**

- **Do not paginate:** Course list (per user), topic list (per course). These are typically small; pagination adds complexity without benefit.
- **Paginate:** Resources per topic (can be large), and any other list that can grow unbounded (e.g. activity feed, search results).

| Area | Improvement |
|------|-------------|
| **List endpoints** | Use pagination only for endpoints that can return large sets (e.g. `GET /api/topics/{topic_id}/resources`). For courses and topics, return full list with indexes and avoid N+1 via `selectinload`/joinedload. |
| **AI-heavy endpoints** | Fact-check, research, test generation, study agent: keep as async; consider **request timeouts** and **per-user rate limits** (e.g. Redis sliding window) so one user can’t starve others. |
| **Response shape** | Paginated endpoints: consistent shape (`items`, `total`, `page`, `page_size`). Non-paginated: simple array or object. Optional ETag for cached lists later. |
| **Compression** | Enable gzip/Brotli in FastAPI (e.g. `GZipMiddleware`) for JSON and large payloads. |

### 1.3 Test submission — single batch request (text + all voice answers)

**Current (inefficient):** Frontend submits text answers in one `POST /tests/{id}/submit`, then loops and calls `POST /tests/{id}/voice-answer` once per voice answer. So 1 + N requests (e.g. 1 + 3 = 4 requests) and sequential latency.

**Target:** One request that accepts both text answers and all voice files; backend creates one attempt, saves all answers, uploads all voice files, enqueues all grading jobs, returns `attempt_id`.

| Layer | Change |
|-------|--------|
| **Backend** | New endpoint e.g.  `POST /api/tests/{test_id}/submit-full` accepting **multipart/form-data**: (1) one JSON part with `answers: [{ question_id, answer_text? }]` and optional `voice_question_ids: string[]`; (2) one file part per voice answer, keyed by question_id (e.g. `voice_<question_id>`). Create single TestAttempt; for each question create TestAnswer (text or placeholder); upload each voice file to storage, set audio_url on corresponding TestAnswer; enqueue all grading jobs; return attempt_id. |
| **Frontend** | Build a single `FormData`: append JSON part, then append each voice file with key `voice_<questionId>`. Call single `submitFull(testId, formData)`; on success redirect to results with attempt_id. Remove the loop over `submitVoiceAnswer`. |
| **Optional** | Keep existing `submit` and `voice-answer` for backward compatibility or remove once frontend is migrated. |

### 1.4 Uploads: frontend direct vs backend

**Current:** All uploads go through the backend (browser → backend → storage). Backend receives the file and uploads to Cloudinary/R2.

**Option — direct upload from frontend:**

- Frontend obtains a **presigned URL** (or Cloudinary unsigned upload params) from the backend via a light endpoint (e.g. `POST /api/upload/presign` with filename, type, purpose).
- Frontend uploads the file **directly to storage** (R2/Cloudinary) using that URL/params.
- Frontend then sends only the **resulting file URL** (and metadata) to the backend for the actual operation (e.g. create resource, submit voice answer).
- **When the backend needs to process the file** (e.g. GPT Vision on an image for resource creation), the backend **downloads** the file from that URL in the same request or worker cycle, then runs vision/transcription. So: no double upload (client→backend→storage), but backend still fetches when it needs to process. Good for reducing backend load.

**Summary:**

- Use **direct upload** where the backend only stores and references the file (e.g. voice answer audio URL, attachment URL).
- For **resource creation with images**, frontend can direct-upload images and send URLs; backend downloads those URLs when running GPT Vision and then creates the resource. Same request cycle from the user's perspective; backend does one download per image when processing.

### 1.5 Database and workers

- **Indexes:** Ensure indexes on foreign keys and frequently filtered/sorted columns (e.g. `topic_id`, `course_id`, `created_at`, `user_id`). Check Alembic for missing indexes.
- **Chunking/embedding:** Ensure workers don’t re-process the same resource twice; use idempotency or “processing” flag.
- **Connection pooling:** Verify async engine pool size matches concurrency (e.g. not too small under load).

### 1.6 Tasks (backend optimization)

- [ ] Add `app/services/cache.py` (Redis get/set/delete with optional pattern invalidation).
- [ ] Add config: `CACHE_ENABLED`, `CACHE_TTL_COURSES`, `CACHE_TTL_TOPICS`, `CACHE_TTL_RESOURCES`.
- [ ] Cache GET courses list and GET course by id (invalidate on course create/update/join).
- [ ] Cache GET topics by course and GET topic by id (invalidate on topic create/update/delete).
- [ ] Cache GET resources by topic only where paginated (invalidate on resource create/update/delete).
- [ ] Add GZipMiddleware (or equivalent) for responses.
- [ ] **Test submission:** Add `POST /api/tests/{test_id}/submit-full` (multipart: JSON + N voice files); create one attempt, all answers, upload all voice files, enqueue all grading jobs; frontend calls this once with all text + voice.
- [ ] **Uploads (optional):** Presigned-URL or direct-upload endpoint; frontend uploads to storage, sends URL to backend; backend downloads from URL only when processing (e.g. vision).
- [ ] Review and add DB indexes where lists are filtered/sorted.
- [ ] Optional: per-user rate limit for AI endpoints (Redis sliding window).

---

## 2. Offline mode (per spec)

**Spec reference:** `NotesOS_Specification_v2.md` — **Appendix D: Offline Mode (Consumption-First)**.

**Philosophy:** Offline = read synced data + create/edit/queue; no offline AI. All intelligence requires internet.

### 2.1 Offline capabilities (from spec)

| Feature | Offline behavior |
|--------|-------------------|
| View notes | Read all synced notes from local store |
| View AI summaries / explanations / fact-check results / quiz Q&A / chat history | Pre-generated/cached only |
| Create text notes | Saved locally, synced on reconnect |
| Edit existing notes | Changes queued for sync |
| Upload images/files | Queued locally, processed on reconnect |
| View course structure | Topics, metadata cached |

### 2.2 Offline limitations (from spec)

| Feature | Offline behavior |
|--------|-------------------|
| AI chat (new messages) | Blocked; show “Offline” message |
| New AI explanations / quiz generation / grading / fact-checking | Blocked; buttons disabled |
| Semantic search | Degraded to local text search |
| Voice transcription / file processing (OCR or multimodal) | Queued; processed on reconnect |

### 2.3 Data storage (IndexedDB)

**Schema (from spec):**

- **Synced data (read-only when offline):** notes (resources), topics, courses.
- **Cached AI artifacts:** e.g. fact-checks, research, conversation history, test results (read-only).
- **Sync queue:** Pending create/update/delete operations (order preserved).
- **Pending uploads:** Files and metadata to upload when online.

**Limits (spec):** ~1000 notes (~50MB), ~500 AI artifacts (~20MB), ~50 pending uploads (~100MB); total ~170MB.

**Implementation:**

- Use **IndexedDB** via a small wrapper or library (e.g. `idb`, or native `indexedDB`).
- Define **stores:** `courses`, `topics`, `resources`, `aiArtifacts`, `syncQueue`, `pendingUploads`.
- **Rehydration:** On app load, if offline, bootstrap UI from IndexedDB; if online, optionally fetch latest and merge.

### 2.4 Sync and rehydration (from spec D.5)

1. **PUSH (when back online):** Process sync queue in order (create notes, apply edits, upload pending files); retry failed items (e.g. max 3).
2. **PULL:** `GET /api/sync?since={lastSyncTime}` — returns changed notes, new notes, deleted IDs, new AI artifacts. *(Backend may need this endpoint if not present.)*
3. **MERGE:** Server wins for AI artifacts; user prompted for note conflicts; apply deletes locally.
4. **CACHE:** Pre-fetch AI artifacts for notes viewed in last 7 days (summaries, explanations, quizzes).

### 2.5 UX states and messaging (from spec D.6)

| State | UI treatment |
|-------|--------------|
| Offline | Yellow banner; AI buttons grayed out with tooltip |
| Queued content | Small “pending sync” icon on notes/uploads |
| Cached AI | Normal display (no extra indicator) |
| Syncing | Spinner in header; progress for uploads |
| Conflict | Modal with diff view |

**Copy:**

- Offline: *“You’re offline. Notes are read-only. Changes sync when online.”*
- AI disabled: *“AI requires internet. Previous conversations still available.”*
- Sync complete: *“All changes synced successfully.”*

### 2.6 Feature flags (from spec D.7)

- `OFFLINE_MODE_ENABLED`
- `MAX_CACHED_NOTES`, `MAX_CACHED_AI_ARTIFACTS`, `CACHE_RETENTION_DAYS`
- `AUTO_SYNC_ON_RECONNECT`, `PREFETCH_AI_ARTIFACTS`

### 2.7 Tasks (offline mode)

- [ ] Add IndexedDB layer: schema (courses, topics, resources, aiArtifacts, syncQueue, pendingUploads), wrapper API.
- [ ] Detect online/offline (navigator.onLine + optional network listener); expose in a small store or context.
- [ ] Offline banner and gray out AI actions when offline; show tooltip with spec message.
- [ ] When online: persist synced data to IndexedDB (courses, topics, resources) and cache AI responses (fact-checks, research, conversations, test results) used in UI.
- [ ] When offline: read from IndexedDB; allow create/edit of notes and queue; queue file uploads.
- [ ] Sync queue: model (operation type, payload, timestamp); process queue on reconnect (order, retries).
- [ ] Backend: add `GET /api/sync?since=...` if missing (return changes since timestamp for the current user).
- [ ] Conflict handling: modal for note conflicts; server wins for AI artifacts.
- [ ] Optional: offline fallback page (e.g. `/offline`) for direct navigations when offline.
- [ ] Config/feature flags for limits and behavior (max cached notes/artifacts, retention, auto-sync, prefetch).

---

## 3. UI/UX improvements

**Reference:** `NotesOS_Design_System.md` — premium, minimalist, glassmorphism, 8px grid, typography hierarchy.

**Goals:** Align all major flows with the design system; improve fact-checking, tests, and information display; consistent loading/empty/error states.

### 3.1 Global alignment with design system

- **Typography:** Use design system scale (`--text-*`, `--font-*`); headings semibold/medium, body normal; line heights 1.2 (headlines), 1.6 (body).
- **Spacing:** 8px grid everywhere; section spacing 48–64px; component padding 16–24px.
- **Colors:** 90% neutral; accent (black) for primary CTAs only; semantic (success/error/warning) muted and sparse.
- **Components:** Glass cards, frosted nav, floating panels per design system; avoid heavy shadows and multiple accent colors.

### 3.2 Fact-checking feature

- **Current pain:** Unclear status, cramped or unclear presentation of results.
- **Improvements:**
  - Clear states: “Not checked” / “Checking…” / “Verified” / “Issues found” with distinct, minimal indicators (icons + one color each).
  - List of claims in a readable, scannable layout (e.g. one row per claim: claim text, status, confidence, short explanation).
  - “View details” or expand for full explanation and sources.
  - If WebSocket is implemented, show “Fact-checking…” and auto-update when done (no manual refresh).
  - Empty state: “No fact-checks yet. Click Verify to check this resource.”

### 3.3 Tests / quiz flow

- **Current pain:** Flow not pretty; information hierarchy unclear.
- **Improvements:**
  - **Test list / generation:** Clear hierarchy (course → “Tests”); card per test with metadata (topic, question count, date); primary CTA “New test” with topic picker and options (count, difficulty) in a clear form or modal.
  - **Taking test:** One question at a time or clear sections; large, readable question text; text input and voice record button visually balanced; progress indicator (e.g. “Question 3 of 10”).
  - **Results:** Summary at top (score, e.g. “7/10”); then per-question: question, your answer, correct/incorrect, feedback; use spacing and typography to separate blocks; “Retake” or “Back to course” as clear secondary actions.

### 3.4 Information display (general)

- **Lists (courses, topics, resources):** Consistent card treatment; primary line = title/name; secondary = metadata (e.g. topic count, date); avoid walls of text.
- **Empty states:** Every list has an empty state: short message + optional illustration or icon + one CTA (e.g. “Create your first course”).
- **Loading states:** Skeleton or subtle spinner aligned with final layout (e.g. card skeletons for lists).
- **Errors:** Inline or toast with clear message and optional “Retry”; no raw stack traces in production.

### 3.5 Tasks (UI/UX)

- [ ] Audit all main pages against design system (typography, spacing, colors, glass components); fix deviations.
- [ ] Fact-check: Redesign status and result list (claim rows, status icon, confidence, expandable explanation/sources); add empty state; optional WebSocket “Checking…” state.
- [ ] Tests: Redesign test list and “New test” flow (topic picker, options); redesign take-test view (question layout, progress, text + voice); redesign results page (score, per-question feedback, actions).
- [ ] Add or refine empty states for courses, topics, resources, tests, progress.
- [ ] Standardize loading (skeletons) and error (message + retry) patterns across these flows.
- [ ] Optional: Add a simple toast or notification system for sync/errors/success.

---

## 4. Multimodal AI for resources (replace OCR)

**Goal:** For image-based inputs, use **GPT Vision (OpenAI)** to transcribe/describe images and create the resource text. OCR (Tesseract, Google Vision, hybrid) is no longer used for this path.

### 4.1 Current flow (to replace for images)

- User uploads image(s) → stored → `FileProcessor` → `hybrid_ocr` (Tesseract ± Google Vision) → text → optional OCR cleaning → chunking/embedding → resource created.
- PDF/DOCX: PDF → pdf2image + OCR or text extraction; DOCX → mammoth. These can stay as-is or later be folded into a “document → AI” path if desired.

### 4.2 New flow (images → GPT Vision → resource)

- **Input:** One or multiple images (upload to storage, get URLs or bytes; see also §1.4 — frontend can direct-upload and send URLs; backend downloads when processing).
- **Processing:** Send image(s) to **OpenAI GPT-4 Vision** (e.g. `gpt-4o`) with a prompt: “Extract all text and meaningful content from this image. Preserve structure (headings, lists) where possible. If handwritten, transcribe accurately. Output plain text or markdown.”
- **Output:** Single transcript/text per “resource” (one resource can still have multiple image files; AI can receive “these N images are one note” and return one combined transcript).
- **Downstream:** Same as today: store content on the resource, run chunking/embedding, optional fact-check/research later. No OCR cleaning step for this path.

### 4.3 Backend changes

| Area | Change |
|------|--------|
| **New service** | e.g. `app/services/vision_transcribe.py`: `async def transcribe_images(image_urls: List[str]) -> str`. Calls **OpenAI GPT-4 Vision** (e.g. `gpt-4o`) with image URLs or bytes, returns combined text. |
| **Config** | `OPENAI_API_KEY` (existing); e.g. `VISION_MODEL=gpt-4o`, max images per request, max tokens for response. |
| **Resource creation** | For image uploads: after upload to storage, call vision transcribe instead of `FileProcessor` + hybrid_ocr. Still create `Resource` + `ResourceFile` records; content = AI transcript. |
| **Workers** | Chunking worker: input is already text (from vision), so no change. Optional: a single “image processing” worker that does upload → transcribe → save content → enqueue chunking. |
| **Deprecation** | Remove or bypass `hybrid_ocr`, and image path in `file_processor` that uses OCR. Keep `ocr_cleaner` only if still used for other sources (e.g. legacy or PDF-extracted text). |

### 4.4 Frontend changes

- No change to “add resource” UX for images: user still selects/upload images.
- Optional: show “Transcribing with AI…” instead of “Processing…” while the new pipeline runs; when WebSocket is in place, use the same “processing status” event.
- If you remove “Reprocess OCR” from the UI, replace with “Re-transcribe” that calls a new endpoint (e.g. `POST /api/resources/{id}/retranscribe`) that re-runs multimodal on the same images.

### 4.5 Tasks (multimodal resources — GPT Vision)

- [ ] Add `app/services/vision_transcribe.py`: input image URLs or bytes, prompt for transcription, call **OpenAI GPT-4 Vision** (e.g. `gpt-4o`), return text.
- [ ] Add config: `VISION_MODEL` (e.g. `gpt-4o`), use existing `OPENAI_API_KEY`, limits (max images, max tokens).
- [ ] In resource upload flow (or chunking worker): for image MIME types, call vision transcribe instead of `file_processor` + hybrid_ocr; set resource content to result.
- [ ] Ensure chunking/embedding runs on the new content; remove or bypass OCR path for images.
- [ ] Deprecate/remove hybrid_ocr usage for new image resources; optionally keep for legacy reprocess only.
- [ ] Optional: `POST /api/resources/{id}/retranscribe` and frontend “Re-transcribe” button.
- [ ] Update docs/CODEBASE_SUMMARY to describe “GPT Vision transcription” instead of OCR for images.

---

## 5. Other improvements (from earlier audit)

These items were highlighted in the initial codebase review and are included here for completeness.

### 5.1 Logout endpoint (backend)

- **Current:** Frontend calls logout then clears tokens locally; backend has no `POST /api/auth/logout`, so the request 404s.
- **Change:** Add `POST /api/auth/logout` that invalidates the refresh token (e.g. set `is_revoked = True` or delete). Frontend calls it before clearing tokens.
- **Task:** [ ] Implement `POST /api/auth/logout` in `backend/app/api/auth.py`; update frontend `api.auth.logout()` to call it and handle response.

### 5.2 WebSocket for resource / fact-check status

- **Current:** Backend broadcasts processing status (chunking, fact-check complete) over `/ws/{course_id}`; frontend does not connect. Fact-check refresh uses delayed polling (e.g. fetch after 2–3 s).
- **Change:** Frontend connects to `/ws/{courseId}` when on a course/topic page; listens for `processing_status`, `fact_check_complete` (or equivalent). Update resource state to show "Processing…" / "Fact-checking…" and auto-refresh fact-checks when done.
- **Tasks:** [ ] Add WebSocket client (e.g. `frontend/src/lib/websocket.ts`); connect on topic page mount, disconnect on unmount. [ ] In resources store or ResourceCard, react to WS events; remove or reduce delayed `fetchFactChecks` polling.

### 5.3 Streak in nav when no course selected

- **Current:** `GlassNav` accepts a `streak` prop and shows it, but only course-scoped pages pass it. On `/courses` (list) no streak is passed.
- **Change:** Either (a) pass a default streak (e.g. from most recently viewed course or a global "current course" from context), or (b) hide the streak UI when no course is selected. Avoid comparing `course.id === currentCourse.code`; use `course.id === currentCourse?.id` where applicable.
- **Task:** [ ] Wire streak on courses list page (e.g. fetch streak for first/most recent course) or hide streak when `currentCourse` is null.

### 5.4 Resource edit and Re-transcribe

- **Current:** Backend has `PUT /api/resources/{id}` (title, description) and `POST /api/resources/{id}/reprocess-ocr`. Frontend ResourceCard has delete and fact-check only; no edit, no reprocess.
- **Change:** Add "Edit" on ResourceCard (modal or inline form for title/description → `PUT /resources/{id}`). For image resources, replace "Reprocess OCR" with "Re-transcribe" that calls `POST /api/resources/{id}/retranscribe` (re-run GPT Vision on same images; see §4). Show loading state and refresh resource when done.
- **Tasks:** [ ] Resource edit UI (title, description). [ ] Re-transcribe endpoint (if not already in §4) and "Re-transcribe" button for image resources; loading + refresh on completion.

---

## Suggested order of work

1. **Backend optimization** — Cache and request handling give immediate benefit and don’t depend on the other pillars.
2. **Multimodal AI for resources** — Replaces a big piece of complexity (OCR) and unblocks a cleaner “add resource” story.
3. **UI/UX** — Improves daily use; can be done in parallel or after 1–2.
4. **Offline mode** — Depends on stable API and sync contract; IndexedDB and sync queue are the heaviest frontend work; do after backend cache and optional `GET /api/sync` are in place.

---

## Doc references

- **Offline:** `NotesOS_Specification_v2.md` — Appendix D (D.1–D.7).
- **UI/UX:** `NotesOS_Design_System.md` (visual identity, color, spacing, typography, glass components, patterns).
- **Current backend:** `backend/app/services/file_processor.py`, `hybrid_ocr.py`; `backend/app/api/resources.py`.

---

**Last updated:** 2026-02-23
