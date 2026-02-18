# NotesOS — Project Completion Plan

**Goal:** Complete all missing frontend features to match backend capabilities and create a polished, production-ready app.

---

## 📋 Overview

**Current Status:** Backend is complete ✅ | Frontend is ~60% complete

**Remaining Work:** 7 major features + polish items

**Estimated Phases:** 4 phases (Foundation → Core Features → Advanced Features → Polish)

---

## 🎯 Phase 1: Foundation & Auth (Critical - Do First)

**Goal:** Fix routing, auth protection, and session management so the app works reliably.

### Task 1.1: Root Route & Redirects
- [ ] Create `frontend/src/app/page.tsx` that:
  - Checks auth state (from store)
  - Redirects authenticated users to `/courses`
  - Redirects unauthenticated users to `/login`
- [ ] Update login/register pages to redirect to `/courses` instead of `/`
- **Acceptance:** `/` always redirects correctly, no 404s

### Task 1.2: Auth Guard & Session Restore
- [ ] Create `frontend/src/app/(main)/layout.tsx` that:
  - Checks `useAuthStore` for `isAuthenticated`
  - If not authenticated, redirects to `/login`
  - On mount, calls `api.auth.getMe()` to validate persisted tokens
  - If `getMe()` fails (401), clears tokens and redirects to `/login`
- [ ] Create `frontend/src/app/(auth)/layout.tsx` that:
  - Redirects authenticated users away from `/login` and `/register` to `/courses`
- **Acceptance:** Protected routes require auth, expired tokens are handled gracefully

### Task 1.3: Logout Endpoint (Backend)
- [ ] Add `POST /api/auth/logout` endpoint in `backend/app/api/auth.py`:
  - Accepts refresh token
  - Invalidates refresh token in DB (set `is_revoked = True` or delete)
  - Returns 200
- [ ] Update frontend `api.auth.logout()` to handle response properly
- **Acceptance:** Logout properly invalidates tokens server-side

**Phase 1 Deliverable:** App has proper routing, auth protection, and session management.

---

## 🎯 Phase 2: Core Features (High Priority)

**Goal:** Implement the main study features that users expect.

### Task 2.1: Progress Tracking
**Files to create/modify:**
- `frontend/src/stores/progress.ts` (new)
- `frontend/src/app/(main)/courses/[courseId]/progress/page.tsx` (new)
- `frontend/src/components/ProgressCard.tsx` (new)
- `frontend/src/components/layout.tsx` (modify - wire streak)

**Steps:**
1. Create progress store:
   - State: `currentStreak`, `courseProgress`, `topicsProgress`, `recommendations`, `activeSession`
   - Actions: `fetchStreak(courseId)`, `fetchCourseProgress(courseId)`, `fetchTopicsProgress(courseId)`, `fetchRecommendations(courseId)`, `startSession(topicId, type)`, `endSession(sessionId)`
2. Wire streak in `GlassNav`:
   - In course pages, call `fetchStreak(courseId)` on mount
   - Pass streak prop to `GlassNav`
3. Create progress page (`/courses/[courseId]/progress`):
   - Show overall mastery, total study time, current streak
   - List topics with mastery bars (from `fetchTopicsProgress`)
   - Show recommendations (weak topics, inactive topics, next topics)
   - Add "Start Study Session" button (calls `startSession`)
4. Auto-track sessions:
   - On topic page load, optionally auto-start a "reading" session
   - On page unload or navigation, end active session
   - Or add explicit "Start Session" / "End Session" buttons
5. Add progress link in course nav (e.g., "Progress" tab or link)

**Acceptance:** Users can see their progress, streak shows in nav, sessions are tracked.

### Task 2.2: Tests / Quizzes
**Files to create/modify:**
- `frontend/src/stores/tests.ts` (new)
- `frontend/src/app/(main)/courses/[courseId]/tests/page.tsx` (new)
- `frontend/src/app/(main)/courses/[courseId]/tests/[testId]/page.tsx` (new)
- `frontend/src/components/TestCard.tsx` (new)
- `frontend/src/components/VoiceRecorder.tsx` (new)

**Steps:**
1. Create tests store:
   - State: `tests`, `currentTest`, `currentAttempt`, `isGenerating`, `isSubmitting`
   - Actions: `generateTest(courseId, topicIds, questionCount, testType)`, `getTest(testId)`, `submitAnswers(testId, answers)`, `submitVoiceAnswer(testId, questionId, audioFile, attemptId)`, `getResults(attemptId)`
2. Create test generation page (`/courses/[courseId]/tests`):
   - Show list of topics (checkboxes)
   - Inputs: question count, test type (practice/quiz/exam)
   - "Generate Test" button → calls `generateTest` → redirects to test page
   - Show list of past tests/attempts (if backend supports)
3. Create test taking page (`/courses/[courseId]/tests/[testId]`):
   - Display questions one at a time or all at once
   - For each question:
     - Text input for text answers
     - "Record Voice Answer" button → opens `VoiceRecorder` component
     - `VoiceRecorder` uses browser `MediaRecorder` API, shows recording state, uploads file
   - "Submit Test" button → calls `submitAnswers` or `submitVoiceAnswer` for each
   - After submit, redirect to results page
4. Create results page (or section):
   - Show score, correct/incorrect answers
   - Show AI feedback for each answer (if available)
   - "Retake" button to generate new test
5. Add "Tests" link in course nav

**Acceptance:** Users can generate tests, take them (text + voice), and see results.

### Task 2.3: Profile & Settings
**Files to create/modify:**
- `frontend/src/app/(main)/profile/page.tsx` (new)
- `frontend/src/components/PersonalitySettings.tsx` (new)
- `frontend/src/components/layout.tsx` (modify - wire profile button)

**Steps:**
1. Create profile page (`/profile`):
   - Show user info: name, email, avatar (if exists)
   - Edit name (if backend supports `PATCH /api/auth/me` with name)
   - Avatar upload (if backend supports it)
2. Create personality settings component:
   - Dropdowns/radios for:
     - Tone: encouraging / direct / humorous
     - Emoji usage: none / moderate / heavy
     - Explanation style: concise / detailed / visual
   - "Save" button → calls `api.auth.updatePersonality(prefs)`
3. Wire profile button in `GlassNav`:
   - `onProfileClick` → navigate to `/profile`
4. Add logout button on profile page

**Acceptance:** Users can view/edit profile and adjust AI personality.

---

## 🎯 Phase 3: Advanced Features (Medium Priority)

### Task 3.1: Global Invites (Class Invites)
**Files to create/modify:**
- `frontend/src/lib/api.ts` (add `api.invites` section)
- `frontend/src/app/(main)/invites/page.tsx` (new)
- `frontend/src/components/InviteCard.tsx` (new)
- `frontend/src/app/(main)/courses/join/page.tsx` (modify - add class code option)

**Steps:**
1. Add `api.invites` to `api.ts`:
   - `createClass(name?)`, `listMyInvites()`, `listClassmates(classId)`, `joinClass(inviteCode)`, `deleteClass(classId)`, `deactivateClass(classId)`
2. Create invites page (`/invites`):
   - "Create Class Invite" button → modal/form → calls `createClass` → shows invite code + share link
   - List my class invites (cards with invite code, classmate count, active status)
   - Actions: view classmates, deactivate, delete
3. Update join course page:
   - Add tab or option: "Join by Class Code"
   - Input for class invite code
   - Calls `joinClass` → shows success with list of courses joined
4. Add "Invites" link in nav (or in profile dropdown)

**Acceptance:** Users can create class invites and join via class code.

### Task 3.2: WebSocket Integration
**Files to create/modify:**
- `frontend/src/lib/websocket.ts` (new)
- `frontend/src/stores/resources.ts` (modify - listen to WS events)
- `frontend/src/components/ResourceCard.tsx` (modify - show processing status)

**Steps:**
1. Create WebSocket client (`websocket.ts`):
   - Function `connectWebSocket(courseId, token)` → returns WebSocket instance
   - Handles reconnection, error handling
   - Parses messages: `{ type: 'processing_status', resource_id, status, progress? }`, `{ type: 'fact_check_complete', resource_id }`, etc.
2. Integrate in topic page:
   - On mount, connect to `/ws/{courseId}?token={token}`
   - On unmount, disconnect
   - Listen for `processing_status` → update resource state (show "Processing..." badge)
   - Listen for `fact_check_complete` → auto-refresh fact checks for that resource
3. Update `ResourceCard`:
   - Show "Processing..." badge when `is_processed === false`
   - Show "Fact-checking..." when fact check is in progress (from WS)
   - Remove delayed `fetchFactChecks` timeout (rely on WS)

**Acceptance:** Real-time updates for resource processing and fact-check completion.

---

## 🎯 Phase 4: Polish & Enhancements (Lower Priority)

### Task 4.1: Topic Management
**Files to modify:**
- `frontend/src/app/(main)/courses/[courseId]/page.tsx`

**Steps:**
1. Add edit topic:
   - Click topic card → edit mode (inline or modal)
   - Form: title, description, week_number
   - Calls `api.topics.update(topicId, data)`
2. Add delete topic:
   - Delete button on topic card → confirm → calls `api.topics.delete(topicId)`
3. Update create topic form:
   - Add description field (textarea)
   - Add week_number field (number input)

**Acceptance:** Users can edit/delete topics and set description/week when creating.

### Task 4.2: Resource Management
**Files to modify:**
- `frontend/src/components/ResourceCard.tsx`

**Steps:**
1. Add edit resource:
   - "Edit" button → modal/form → title, description
   - Calls `api.resources.update(resourceId, data)`
2. Add reprocess OCR:
   - "Reprocess OCR" button (for image resources with low confidence)
   - Calls `api.resources.reprocessOCR(resourceId)`
   - Shows loading state → refreshes resource on completion

**Acceptance:** Users can edit resources and reprocess OCR.

### Task 4.3: Batch Create (Optional)
**Files to create/modify:**
- `frontend/src/app/(main)/courses/new/page.tsx` (add batch option)
- `frontend/src/app/(main)/courses/[courseId]/page.tsx` (add batch topics option)

**Steps:**
1. Add batch create courses:
   - Toggle "Create Multiple" → shows textarea for JSON or CSV
   - Parses input → calls `api.courses.batch(data)`
2. Add batch create topics:
   - Similar UI in course page
   - Calls `api.topics.batch(courseId, data)`

**Acceptance:** Power users can create multiple courses/topics at once.

### Task 4.4: Error Handling & UX
**Files to create/modify:**
- `frontend/src/components/ErrorBoundary.tsx` (new)
- `frontend/src/app/layout.tsx` (wrap with ErrorBoundary)

**Steps:**
1. Create error boundary component
2. Add global error toast/notification system (if not exists)
3. Improve loading states (skeletons everywhere)
4. Add empty states (no courses, no resources, etc.)

**Acceptance:** App handles errors gracefully, shows helpful messages.

---

## 📊 Progress Tracking

### Phase 1: Foundation & Auth
- [ ] Task 1.1: Root Route & Redirects
- [ ] Task 1.2: Auth Guard & Session Restore
- [ ] Task 1.3: Logout Endpoint

### Phase 2: Core Features
- [ ] Task 2.1: Progress Tracking
- [ ] Task 2.2: Tests / Quizzes
- [ ] Task 2.3: Profile & Settings

### Phase 3: Advanced Features
- [ ] Task 3.1: Global Invites
- [ ] Task 3.2: WebSocket Integration

### Phase 4: Polish & Enhancements
- [ ] Task 4.1: Topic Management
- [ ] Task 4.2: Resource Management
- [ ] Task 4.3: Batch Create
- [ ] Task 4.4: Error Handling & UX

---

## 🚀 Getting Started

**Recommended Order:**
1. **Start with Phase 1** (Foundation) — This makes everything else work properly
2. **Then Phase 2** (Core Features) — These are the main value propositions
3. **Then Phase 3** (Advanced Features) — Nice-to-haves that differentiate the product
4. **Finally Phase 4** (Polish) — Make it production-ready

**For each task:**
1. Read the task description
2. Check existing code patterns (stores, components, API calls)
3. Implement following the same patterns
4. Test manually
5. Check off the task ✅

---

## 📝 Notes

- **Consistency:** Follow existing patterns (Zustand stores, GlassCard UI, API client structure)
- **Testing:** Test each feature manually after implementation
- **Documentation:** Update `CODEBASE_SUMMARY.md` as you complete features
- **Backend:** All backend APIs are ready; focus on frontend implementation

---

**Last Updated:** 2026-02-18
