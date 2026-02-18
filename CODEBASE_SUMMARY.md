# NotesOS — Codebase Summary

**Purpose:** Clear list of what exists (backend + frontend) and what is still missing so you can plan frontend work.

---

## 1. Product vision (from README)

- **Shared Knowledge Pool** — Collaborative note sharing
- **AI Study Partner** — Personalized AI with adjustable personality
- **Voice-First Studying** — Record answers, get AI grading
- **Fact Checker** — Automatic verification of note claims
- **Pre-Class Research** — AI-generated topic primers
- **Progress Tracking** — Mastery levels and study streaks

**Stack:** Next.js 14, React, Zustand, Tailwind, shadcn-style UI · FastAPI, LangGraph/LangChain · PostgreSQL + pgvector, Redis · Cloudflare R2.

---

## 2. Backend — What You Have (Implemented)

### 2.1 API surface (all under `/api/*` or `/api/auth`, etc.)

| Area | Prefix / Path | Endpoints |
|------|----------------|-----------|
| **Auth** | `/api/auth` | `POST /register`, `POST /login`, `POST /refresh`, `GET /me`, `PATCH /me/personality` |
| **Courses** | `/api/courses` | `GET /`, `POST /`, `POST /join`, `GET /{id}`, `POST /{id}/topics`, `POST /batch`, `POST /{id}/topics/batch` |
| **Topics** | `/api` | `GET /courses/{course_id}/topics`, `POST /courses/{course_id}/topics`, `GET /topics/{id}`, `PUT /topics/{id}`, `DELETE /topics/{id}` |
| **Resources** | `/api` | `GET /topics/{topic_id}/resources`, `POST /topics/{topic_id}/resources/text`, `POST /resources/upload`, `GET /resources/{id}`, `PUT /resources/{id}`, `DELETE /resources/{id}`, `POST /resources/{id}/reprocess-ocr` |
| **Invites (global class)** | `/api/invites` | `POST /global`, `GET /global`, `GET /global/{class_id}/classmates`, `POST /global/join`, `DELETE /global/{class_id}`, `PATCH /global/{class_id}/deactivate` |
| **AI features** | `/api` | Fact check: `POST /resources/{id}/fact-check`, `GET /resources/{id}/fact-checks` · Research: `POST /topics/{id}/research`, `GET /topics/{id}/research` · Study: `POST /study/ask`, `GET /study/conversations`, `GET /study/conversations/{id}` · Tests: `POST /tests/generate`, `GET /tests/{id}`, `POST /tests/{id}/submit`, `POST /tests/{id}/voice-answer`, `GET /tests/attempts/{attempt_id}/results` |
| **Progress** | `/api/progress` | `POST /sessions/start`, `POST /sessions/{id}/end`, `GET /{course_id}`, `GET /{course_id}/topics`, `GET /{course_id}/streak`, `GET /{course_id}/recommendations` |
| **WebSocket** | `/ws/{course_id}?token=...` | Real-time course updates (e.g. processing status, active users) |

**Note:** Backend has **no** `POST /api/auth/logout`; frontend calls it and then clears tokens locally, so logout “works” but the request 404s.

### 2.2 Backend structure (high level)

- **`app/main.py`** — FastAPI app, CORS, lifespan (DB init, Redis listener), all routers, WebSocket.
- **`app/config.py`** — Settings (DB, Redis, JWT, R2, feature flags like `ENABLE_FACT_CHECK`, etc.).
- **`app/database.py`** — Async engine/session, `init_db`, `get_db`.
- **`app/models/`** — User, RefreshToken, Course, CourseEnrollment, Topic, CourseOutline, Resource, ResourceFile, FactCheck, PreClassResearch, Test, TestQuestion, TestAttempt, TestAnswer, StudySession, UserProgress, AIConversation, AIMessage, Class, Classmate.
- **`app/api/`** — auth, courses, topics, resources, invites, ai_features, progress.
- **`app/services/`** — fact_checker, storage, file_processor, ocr_cleaner, hybrid_ocr, chunking, embeddings, vector_store, rag, study_agent, research_generator, question_generator, transcription, grader, progress, redis_client, websocket.
- **`app/workers/`** — chunking_worker, grading_worker, fact_check_worker (Redis-based async jobs).

So: auth, courses, topics, resources, invites, AI (fact-check, research, study agent, tests), progress, and WebSocket are all implemented on the backend.

---

## 3. Frontend — What You Have (Implemented)

### 3.1 Routing and pages

| Route | Page | What it does |
|-------|------|----------------|
| `/login` | Login | Email/password, redirect to `/` on success. |
| `/register` | Register | Full name, email, password, redirect to `/`. |
| **No root `/` page** | — | Login/register redirect to `/`; there is no `app/page.tsx`, so `/` will 404. |
| `/courses` | Courses list | List enrolled courses, “Join Course” and “Create Course” links. |
| `/courses/new` | Create course | Form: code, name; redirect to new course. |
| `/courses/join` | Join course | Single field (invite code or search); joins then redirect to `/courses`. |
| `/courses/[courseId]` | Course home | Topic list with mastery bars, “Add topic” form. |
| `/courses/[courseId]/topics/[topicId]` | Topic study | Pre-class research (collapsible), resources (upload files / write notes), resource cards with fact-check, floating AI chat overlay. |

There is **no** route group layout under `(main)` or `(auth)` that enforces auth or redirects; protection is effectively “if you hit an API without a token, you get 401 and the client redirects to `/login`” (in `api.ts`).

### 3.2 API client and stores

- **`src/lib/api.ts`** — Axios instance, JWT + refresh in interceptors, and a full `api` object matching the backend:
  - **auth:** register, login, logout, refresh, getMe, updatePersonality
  - **courses:** getAll, getById, create, join
  - **topics:** getByCourse, create, getById, update, delete
  - **resources:** getByTopic, createText, upload, getById, update, delete, reprocessOCR
  - **ai:** verifyResource, getFactChecks, generateResearch, getResearch, askQuestion, getConversations, getConversation, generateTest, getTest, submitAnswers, submitVoiceAnswer, getTestResults
  - **progress:** startSession, endSession, getCourseProgress, getTopicsProgress, getStreak, getRecommendations

- **Stores (Zustand):**
  - **auth** — user, login, register, logout, updatePersonality, persisted (user + isAuthenticated).
  - **courses** — courses list, currentCourse, fetchCourses, createCourse, joinCourse, selectCourse, createTopic, persisted (currentCourse).
  - **resources** — resources list, fetchResources, createTextResource, uploadFiles, deleteResource, factCheckResource, fetchFactChecks, pagination, factChecks per resource.
  - **aiChat** — conversations, messages, fetchConversations, loadConversation, askQuestion, clearCurrentConversation.
  - **index** — re-exports auth and courses (not resources or aiChat).

### 3.3 UI and components

- **Layout:** `GlassNav` (logo, course switcher dropdown, streak placeholder, profile button), `MainLayout` (nav + main content). Streak is passed as prop but **never loaded from API** on any page.
- **UI primitives:** `GlassCard`, `PageHeader`, `Button`, `Input`, `Badge`, `Skeleton` (in `components/ui.tsx`).
- **Feature components:** `ResourceCard` (markdown, files, fact-checks, delete, verify), `FileUpload` (drag-and-drop, progress), `MarkdownRenderer`, `AIChat`, `AIChatOverlay` (floating button + full-screen modal).

So on the frontend you have: auth flows, course list/create/join, course detail with topics, topic detail with research + resources + fact-check + AI chat. The API client and stores are ready for progress, tests, and invites; the UI for those is missing.

---

## 4. What’s Still Missing (Frontend-Focused)

### 4.1 Critical / UX

1. **Root route `/`**  
   - Login/register redirect to `/`. Add either `app/page.tsx` that redirects to `/courses` (or `/login` if not authenticated), or a middleware that sends `/` → `/courses` or `/login`.

2. **Auth guard and session restore**  
   - No layout or middleware that redirects unauthenticated users from `/courses/*` to `/login`.  
   - On load, if the user has a persisted session (Zustand + tokens), consider validating with `GET /api/auth/me` and redirecting to login on 401.

3. **Logout endpoint (optional)**  
   - Backend has no `POST /api/auth/logout`. Either add it (e.g. invalidate refresh token) or keep current behavior (frontend clears tokens and calls a non-existent logout; works but logs 404).

### 4.2 Not implemented in UI (backend and API client ready)

4. **Progress**
   - **API:** start/end session, course progress, topic progress, streak, recommendations.
   - **Missing:** No progress store usage in UI. No page or section for “today’s streak”, “study time”, “mastery by topic” (course page shows a mastery bar but data is not loaded from progress API). No “start session” / “end session” flows.

5. **Tests / quizzes / voice answers**
   - **API:** generate test, get test, submit text answers, submit voice answer, get attempt results.
   - **Missing:** No tests store. No UI to: pick topics → generate test → take quiz (text or voice) → see results. No test list or “retake” flow.

6. **Global invites (class invites)**
   - **API:** create class invite, list my invites, list classmates, join by class code, delete/deactivate.
   - **Missing:** No `api.invites` in the frontend (no client methods). No UI to create/share a “class link” or join via class code so that one join enrolls in all of the inviter’s courses.

7. **Course/topic batch create**
   - **Backend:** `POST /api/courses/batch`, `POST /api/courses/{id}/topics/batch`.
   - **Missing:** No UI to create multiple courses or topics at once.

### 4.3 Partially implemented or polish

8. **Streak in nav**
   - `GlassNav` accepts `streak` and shows it. No page passes it; no one calls `api.progress.getStreak(courseId)`. So either wire streak (e.g. from course context or a global “current course” streak) or remove the placeholder.

9. **Profile / settings**
   - **Backend:** `PATCH /api/auth/me/personality` (tone, emoji_usage, explanation_style).
   - **Missing:** No profile or settings page. No way to change name, avatar, or study personality from the UI (only API exists).

10. **WebSocket**
    - Backend broadcasts processing status (e.g. chunking, fact-check) over `/ws/{course_id}`.
    - **Missing:** Frontend does not open the WebSocket or show “Processing…” / “Done” for resources; fact-check refresh is done with a delayed `fetchFactChecks` (e.g. after 2–3 s).

11. **Resource update**
    - **API:** `PUT /api/resources/{id}` (e.g. title, description).
    - **Missing:** No edit resource UI (only delete and fact-check on `ResourceCard`).

12. **Topic update/delete**
    - **API:** `PUT /api/topics/{id}`, `DELETE /api/topics/{id}`.
    - **Missing:** Course page has no edit/delete topic; only create.

13. **Topic description / week**
    - Create topic form only sends title and order_index; description and week_number exist in API but are not in the form.

14. **Reprocess OCR**
    - **API:** `POST /api/resources/{id}/reprocess-ocr`.
    - **Missing:** No button or flow in the UI to trigger reprocess.

15. **Course switcher highlight**
    - In `GlassNav`, the dropdown compares `course.id === currentCourse.code` (id vs code); it should compare `course.id === currentCourse?.id`. Fixed in layout; keep an eye on any similar comparisons.

16. **shadcn/ui**
    - README mentions shadcn/ui; current UI is custom (e.g. `GlassCard`, `Button` in `ui.tsx`). Either adopt shadcn for new components or treat the current set as the design system.

### 4.4 Nice to have

- **PWA:** `next-pwa` is in package.json; no check of manifest or service worker in this summary.
- **Error boundaries / global error state** for API errors beyond per-page/store error.
- **Accessibility:** No audit done; worth a pass for forms and keyboard/navigation.

---

## 5. Quick reference: backend vs frontend

| Feature | Backend | Frontend API client | Frontend UI |
|--------|---------|---------------------|------------|
| Auth (register, login, refresh, me, personality) | ✅ | ✅ | ✅ Login, Register; ❌ profile/settings |
| Courses (CRUD, join, batch) | ✅ | ✅ (no batch) | ✅ List, create, join; ❌ batch |
| Topics (CRUD, batch) | ✅ | ✅ (no batch) | ✅ List, create; ❌ edit/delete, batch, description/week in form |
| Resources (list, text, upload, get, update, delete, reprocess-ocr) | ✅ | ✅ | ✅ List, create text, upload, delete, fact-check; ❌ edit, reprocess OCR |
| Fact check | ✅ | ✅ | ✅ Trigger + show fact checks |
| Pre-class research | ✅ | ✅ | ✅ Generate + show (collapsible) |
| Study agent (ask, conversations) | ✅ | ✅ | ✅ Overlay chat |
| Tests (generate, submit, voice, results) | ✅ | ✅ | ❌ No UI |
| Progress (sessions, course/topic, streak, recommendations) | ✅ | ✅ | ❌ No UI; streak slot in nav unused |
| Global invites (class) | ✅ | ❌ No client | ❌ No UI |
| WebSocket | ✅ | ❌ | ❌ No connection |
| Logout | ❌ No endpoint | ✅ (calls then clear) | ✅ Button/flow exists |

---

## 6. Suggested order to tackle (frontend)

1. **Root + auth guard** — Add `/` (redirect) and protect `/courses/*` so unauthenticated users go to `/login`; optionally restore session with `getMe`.
2. **Progress** — Use progress API and store (or minimal state) to show streak in nav and a simple “progress” or “today” section (e.g. on course or dashboard).
3. **Tests / quizzes** — Add a tests store and flows: choose course/topics → generate → take test (text + voice) → results.
4. **Global invites** — Add `api.invites` and a small “Invite classmates” / “Join with class code” UI.
5. **Profile/settings** — One page for name + study personality (and optionally avatar) using `PATCH /me` and `PATCH /me/personality`.
6. **WebSocket** — Connect to `/ws/{course_id}` and drive “Processing…” / “Done” for resources and fact-check.
7. **Polish** — Topic edit/delete, resource edit, reprocess OCR, batch create (if needed).

Use this doc as the single “what I have / what’s missing” list and update it as you implement each piece.
