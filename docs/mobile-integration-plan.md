# NotesOS — Mobile ↔ Backend Integration Plan (tracking doc)

> **This is the tracking doc for the whole mobile↔backend integration effort** — not a
> one-session handoff note. It covers everything we want to do to take `mobile/` (19
> screens, ported from a Claude Design System export, currently mock-data-driven) from
> scaffolding to a real client wired against the v2 backend. Any agent or session
> picking up this work should start here, update the queue as work lands, and append to
> the log — never delete history, never silently mark something done without wiring it
> to a real endpoint.
>
> Work happens **step by step, one screen/flow at a time** — explicit user preference.
> Don't batch multiple screens into one pass unless asked to.
>
> Last updated: 2026-07-26. Branch: `v2`.

---

## 0. How to use this doc

- **Section 1** — decisions already locked in. Don't re-litigate without the user raising it again.
- **Section 2** — the build queue: every screen/flow that needs wiring, in the order it makes sense to tackle, with checkboxes. This is the thing to update most often.
- **Section 3** — session-by-session work log. Append, don't rewrite history.
- **Section 4** — known gaps / traps for whoever picks this up next.
- **Section 5** — explicitly deferred / out-of-scope — do not start unprompted.

---

## 1. Locked decisions

- **Auth model: phone is the primary identity.** Required, unique, password-based. This
  was a direct correction after an earlier pass wrongly made email primary — the user's
  exact words: *"phone is still the primary - it just also require a password when
  login in - literary same as when we do email password."* Email stays optional. Do not
  swap this back to email-primary.
- **No OTP anywhere.** Register/login issue tokens immediately on valid
  phone+password. Google OAuth still requires attaching a phone for a new identity, but
  that step is also OTP-free (see `backend/app/api/auth.py`).
- **Google OAuth is not shipping at launch — but the backend support stays.** User's
  words: *"no google auth integration. its not necessary"*, then clarified when I
  started scoping a removal: *"dont remove the support it just wont be shipped with
  launch."* Net effect: `backend/app/api/auth.py`'s `/google`, `/google/callback`,
  `/oauth/register` endpoints and the `User.google_id` column stay in place, untouched,
  for future use. The mobile app just doesn't build a UI for it — the dead
  "Continue with Google" button was removed from `login.tsx` (2026-07-26) since a
  visible button that does nothing is worse than no button. If Google sign-in is wanted
  later, the backend flow already exists and is tested; only the mobile side (in-app
  browser / deep-link handling) needs building.
- **No backend reports/moderation endpoint.** Explicitly rejected by the user mid-build:
  *"no dont inclue the report side - the app does taht it self - dont add it."* If a
  `Report` model, `api/reports.py`, or a reports router registration reappears, that's a
  regression — remove it unless the user asks again from scratch.
- **The UI is scaffolding, not final.** It was built by a system with no backend
  context. Expect drift: some screens will need rework, rearrangement, or don't map
  cleanly to a real endpoint yet. Some pages are even missing outright. That's expected
  — flag drift to the user rather than inventing backend behavior to force-fit the mock
  UI.
- **Retrieval-mode picker UI is a known complaint, explicitly parked.** User's words:
  *"i dont like the way the UI presents its - just as a list but it should be context
  worthy and also be spread out across the platform... i dont really know what that'll
  be like but when we get there we'll talk about it."* Wiring `retrieval.tsx` to real
  data is fine; redesigning its layout is not, until the user brings it up again.

---

## 2. Build queue

Legend: ✅ done & verified · 🟡 in progress / partially wired · ⬜ not started

Ordered roughly by dependency (auth → identity/profile → course/topic structure →
content → retrieval/study loop → ambient features). Reorder if the user asks to jump
around — this is a queue, not a strict gate.

### 2.1 Auth ✅ (done for launch scope)

- [x] Backend: phone+password register/login, no OTP, immediate tokens
- [x] Backend: Google OAuth phone-attach flow (no OTP) — kept, not wired to mobile, see §1
- [x] Backend tests (`test_auth.py`, `test_user_signals.py`) — 73/73 passing
- [x] Mobile: `lib/auth.ts` (SecureStore token persistence)
- [x] Mobile: `lib/api.ts` (axios client, JWT interceptor, 401 refresh-and-retry)
- [x] Mobile: `login.tsx` wired to real register/login
- [x] Mobile: `index.tsx` cold-start session check
- [x] Mobile: `login.tsx` — removed the dead "Continue with Google" button/copy (not shipping at launch, see §1)
- [x] Mobile: `settings.tsx` sign-out button — wired to `clearTokens()` + `router.replace('/login')`

Auth is closed out for launch. Google sign-in on mobile is post-launch, tracked in §5, not this queue.

### 2.2 Onboarding ⬜

- [x] Map `onboarding.tsx` profile fields to `PATCH /api/auth/me` (school_name, program, entry_year) — done 2026-07-26
- [x] Wire school picker/search to `GET /api/schools/search` (live debounced typeahead + "use as typed" fallback) — done 2026-07-26
- [x] Onboarding tail reworked to the §6 flow (cohort→create→invite) — done 2026-07-26.
  Mock catalog/code "setup" step removed; `CourseAcquisition` component + `lib/courses.ts`
  drive it. Contact-match (final beat) is still pending as §6.4 step 4.

### 2.3 Courses ✅ (wired 2026-07-27)

- [x] `courses.tsx` — list/read from `api/courses.py` (`fetchMyCourses()`), grouped by
  `term_label` (null → "Your courses"), real loading/empty states, refetch-on-focus, rows
  route to `/topics?courseId=…`. Mis-routed "Join with a code" (was `/topics`) → `/coursejoin`.
- [x] `coursecreate.tsx` — now reuses `<CourseAcquisition/>` (cohort→create→proximity→invite,
  native Share, force-create fallback). Mock MATCHES/name-only form gone. Mis-routes fixed by
  reuse ("Join this one" → `joinCourse`, "Make my own anyway" → force-create).
- [x] Course invite/join flow — NEW `coursejoin.tsx` modal (registered in `_layout.tsx`):
  one invite-code Input → `joinCourse({inviteCode})` → back to `/courses`.

### 2.4 Discovery 🟡

- [x] `discovery.tsx` — wired to `api/discovery.py` (2026-07-27). `lib/discovery.ts` typed
  client; "Courses to join" **merges classmate-overlap (`/discovery/courses`) + cohort
  (`/discovery/cohort`), deduped by course id**, so it isn't empty for a new user;
  `courseReason()` labels each by strongest signal. "Classmates" from `/discovery/classmates`.
  Join → `POST /api/courses/join` (marks "Joined ✓" in place; notify-don't-enroll). Real
  empty states replace the old mock `CLASSMATES`/`COURSES`. tsc + lint clean; not yet run
  on a device.
- [ ] **Note:** the onboarding-time discovery experience is part of the §6 epic and needs
  NEW backend (contact-match + cohort). Today's `api/discovery.py` is enrollment-overlap
  only and is **empty for a brand-new user** — it becomes useful only after they have ≥1
  course. Don't wire onboarding to it expecting results.

### 2.5 Topics & resources 🟡

- [x] `topics.tsx` — wired 2026-07-27. Consumes the `courseId` param from the course row,
  fetches `GET /api/courses/{id}` (course header + topics in one enrollment-checked call)
  via `fetchCourseTopics()` in `lib/topics.ts`. Real loading/empty/error states, refetch-
  on-focus. Rows route to `/note` carrying `topicId`+`courseId`; "Add material" carries
  `courseId` into `/capture`. **Drift flagged:** the mock's per-topic status badge
  (ready/synthesizing/empty) + resource count aren't in any list endpoint — they live only
  on `GET /api/topics/{id}` (an N+1 the backend avoids in lists) and belong to the note
  surface. Dropped from the list rather than faked; subtitle is description → week → "No
  description yet". **The user likes this badge and wants it back — see the scoped backend
  enhancement below.**
- [ ] **Backend enhancement — topic status + resource count in the topic list (WANTED,
  user 2026-07-27).** Restore the per-topic badge (empty / synthesizing / ready) + a
  resource count on `topics.tsx`. Scope:
  - **Data (no new models, no migration):**
    - `resource_count` — batch `SELECT topic_id, count(*) FROM resources WHERE topic_id IN (…) GROUP BY topic_id` (`Resource.topic_id` exists).
    - synthesis state — `TopicKnowledge.status` (`KnowledgeStatus`: pending/processing/completed/failed), one row per topic (`topic_id` unique). Batch `SELECT topic_id, status FROM topic_knowledge WHERE topic_id IN (…)`.
  - **Derive (server-side helper):** `empty` = resource_count 0; `synthesizing` = has
    resources AND (no knowledge row yet OR status in {pending, processing}); `ready` =
    status == completed. (`failed` → optional "needs attention" state, defer.)
  - **Where:** embed `status` + `resource_count` per topic into the array
    `GET /api/courses/{id}` already returns (what `topics.tsx` calls) — keeps it one call.
  - **The real cost is cache coherence, not the query.** `course_key` + `topics_list_key`
    are cached; today a resource add or a synthesis-completion doesn't reliably bust them,
    so a topic could show "synthesizing" forever from cache. Must invalidate both keys on:
    (a) resource add/delete (resources router + **capture worker**), and (b)
    `knowledge_worker` transitioning a topic to COMPLETED. That worker-side invalidation is
    the part needing care + tests (vs. real Postgres).
  - **Effort:** small–medium backend (2 batched queries + derive helper + cache-invalidation
    hooks + tests); tiny mobile (re-add badge/count, extend `CourseTopic`). Additive,
    low-risk. Escalate only if we want the richer failed/needs-review states.
- [x] `capture.tsx` — wired 2026-07-27 with **live WebSocket progress** (user chose live
  over fire-and-forget; files + photos over files-only). Flow: pick (documents / camera /
  library) → upload each to Cloudinary directly (unsigned preset, `lib/cloudinary.ts`) →
  `POST /api/courses/{id}/capture` (`lib/capture.ts`) → 202 + `batch_id` → subscribe to the
  course room (`lib/courseSocket.ts`) → drive stages off `capture_progress`
  (transcribing → organizing) → `capture_complete` shows the filed topics (title + item
  count + "to check" for low-OCR-confidence) / `capture_failed` shows an error. "Back to
  course" returns to topics (refetches on focus). **Drift dropped:** the mock's
  "confirm structure" step has no backend — the worker auto-files without asking — so the
  final screen is a *result*, not an approval gate. "Paste text" isn't a capture input
  (capture is files-only) so it's gone too.
  - **⚠️ Owner actions:** (1) set `EXPO_PUBLIC_CLOUDINARY_CLOUD_NAME` +
    `EXPO_PUBLIC_CLOUDINARY_UPLOAD_PRESET` (public, unsigned — mirrors the web's
    `NEXT_PUBLIC_CLOUDINARY_*`); (2) **rebuild the dev client** — `expo-document-picker` +
    `expo-image-picker` are native modules (installed at `~57.0.x` via
    `npm install … --ignore-scripts`).
- [ ] `source.tsx` — wire to `api/resources.py` (file upload & retrieval)

### 2.6 Note / knowledge ⬜

- [ ] `note.tsx` — wire to `api/knowledge.py`. **Read `docs/system-spec.md` before building this one** — this is the "note = root of retrieval tree" surface, structure-first synthesis, mastery heat-map (see `[[note-lit-by-mastery-kept]]` memory — the full heat-map is the design, not decoration, don't simplify it away).

### 2.7 Retrieval / study loop ⬜

- [ ] `retrieval.tsx` — wire to `api/retrieval.py` (`POST /next`, `POST /attempt`, `GET /modes`). Layout stays as-is per §1 parked complaint — wire data only.
- [ ] `testbuilder.tsx` — wire to `api/practice_test.py` (B14 authored practice test). This is a **distinct concept** from `retrieval.tsx`'s scheduled review — see `[[authored-practice-test]]` memory. Don't merge them.

### 2.8 Voice / audio ⬜

- [ ] `listen.tsx` / `voice.tsx` — wire to `api/voice.py` (WS `/ws/voice/{course_id}`). Confirm premium-lane gating before wiring (architecture docs flag this as a premium feature).

### 2.9 Notifications ⬜

- [ ] `notifications.tsx` — wire to `api/notifications.py`. Check whether WebSocket push (`services/websocket.py`) or polling is the intended pattern for mobile (mobile can't rely on the same browser WS assumptions as the Next.js frontend — verify reconnect-on-background behavior).
- **Foundation landed 2026-07-27:** `lib/courseSocket.ts` — a minimal course-room WS client
  (`WS /ws/{course_id}?token=`, heartbeat, backoff reconnect, 1008=auth-stop), built for
  capture's live progress. It's the seed for this section. Still TODO for full §2.9:
  **reconnect-on-background** (AppState-aware — RN backgrounding drops the socket) and the
  user-scoped `/ws/user/{user_id}` channel for personal notifications.

### 2.10 Settings / profile ⬜

- [x] Sign-out — wired under §2.1, lives on this screen
- [ ] `settings.tsx` — wire remaining fields: `PATCH /me`, `/me/personality`, `/me/preferences`, `/me/change-password`

### 2.11 Cross-cutting / not yet screen-specific

- [ ] Global error/toast handling for API failures (currently ad hoc per-screen, e.g. `login.tsx`'s inline error text — decide if this should become a shared pattern)
- [ ] Loading/empty states once real data replaces mocks (some mock states may not have real equivalents — e.g. empty course list, zero-mastery note)
- [ ] Decide `EXPO_PUBLIC_API_URL` handling for real device testing vs. simulator (see §4)

---

## 3. Session work log

### 2026-07-26 — Auth foundation (phone+password, no OTP) + mobile API client

**Backend:**
- `models/user.py` — phone required/unique/primary; email optional; removed
  `phone_verified`/`phone_otp`/`phone_otp_expires` columns entirely.
- `api/auth.py` — rewritten: `POST /register` and `POST /login` (phone+password,
  immediate token issuance), Google OAuth simplified to a phone-attach step with no OTP
  (`POST /oauth/register` via a short-lived intent JWT, `create_oauth_register_token`/
  `decode_oauth_register_token`). Removed `/verify-otp`, `/otp/resend`,
  `OtpPendingResponse`, `issue_otp()`.
- `services/otp.py` — deleted (confirmed no remaining references outside historical
  Alembic migration filenames).
- `config.py` — removed `OTP_PROVIDER`/`OTP_EXPIRE_MINUTES`; kept
  `OAUTH_REGISTER_TOKEN_EXPIRE_MINUTES`.
- Tests: `test_auth.py`, `test_user_signals.py` rewritten for the new flow;
  `conftest.py`'s `register_user` fixture updated. 73/73 tests touching `User` pass
  (auth, user_signals, courses, enrollment, proximity, terms, discovery, sync), plus one
  full clean suite run before the shared test-Postgres container got flaky on repeated
  back-to-back full-suite runs (see §4).
- Built, then **fully reverted**, a reports feature (`models/report.py`,
  `api/reports.py`, router registration) per direct user instruction — nothing reports-
  related should exist on disk; if it does, that's a regression, not this doc's intent.

**Mobile:**
- Added `axios`, `expo-secure-store` (installed via `npm install ... --ignore-scripts`
  — `npx expo install` fails in this sandbox with `EALLOWSCRIPTS`, see §4).
- New `mobile/src/lib/auth.ts` — SecureStore token persistence
  (`getAccessToken`/`getRefreshToken`/`setTokens`/`clearTokens`).
- New `mobile/src/lib/api.ts` — shared axios instance, JWT request interceptor, 401
  response interceptor with single-flight refresh-and-retry.
- `login.tsx` rewritten: dropped the OTP stage, added a password field, wired real
  register/login calls, stores tokens on success. Google button still a no-op.
- `index.tsx` rewritten: checks for a stored token on cold start, routes to `/home` or
  `/login` accordingly (previously always `/login`).
- Verified with `npx tsc --noEmit` (zero errors) after each edit.

**Net effect:** §2.1 (Auth) essentially done, two small items left (Google OAuth
button, sign-out). Every other section in §2 is still ⬜.

### 2026-07-26 — Auth closed out: sign-out wired, Google button dropped from launch

- User call: *"lets wrap up auth. note -> no google auth integration. its not
  necessary"* — then, after I started scoping what to remove: *"dont remove the support
  it just wont be shipped with launch."* See §1 for the full decision.
- Backend: **no changes.** `/google`, `/google/callback`, `/oauth/register` and
  `User.google_id` stay exactly as they are — untouched, still tested, just not
  consumed by mobile.
- Mobile: `settings.tsx` — `Sign out` row now calls `clearTokens()` then
  `router.replace('/login')` (was a no-op `onPress={() => {}}`).
- Mobile: `login.tsx` — removed the "Continue with Google" button, the "or" divider,
  and its supporting copy. The submit button + phone/password fields are now the whole
  form.
- Verified with `npx tsc --noEmit` (zero errors).
- §2.1 (Auth) is now fully closed for launch scope. Next queue item is §2.2 Onboarding.

---

### 2026-07-27 — Contact-match mobile UI + global-phone + unauth-redirect fixes

- **Contact-match UI shipped** (§6.4 step 4 mobile portion — see that entry for the file
  list): `lib/phone.ts`, `lib/contacts.ts`, `app/contacts.tsx`, wired as onboarding's
  final beat, `expo-contacts` plugin added to `app.json`.
- **Global phone identity (user call: *"this product is global"*).** `login.tsx` now
  canonicalises the phone to **E.164 via `lib/phone.ts` (device-region aware)** before
  register/login. This makes the stored identity — and the contact-match hash — region-
  independent: the server's NG-region canonicalisation becomes a no-op on already-E.164
  input, so a non-NG user who types a national number on their own device still gets the
  correct hash. Closes the caveat noted in §6.5.
- **Unauth → login redirect (bug: landing on a protected page showed a page error).**
  Root cause: protected screens fetch on mount, hit a 401 that can't be refreshed (no
  token), and the axios interceptor just rethrew → the page rendered its own error state.
  Fix in `lib/api.ts`: on an unrecoverable 401 for a **non-auth** request, it clears tokens
  and `router.replace('/login')`. Auth endpoints (`/login`, `/register`, `/refresh`) are
  exempt so login's own "wrong password" 401 still surfaces its message instead of
  bouncing. `index.tsx`'s cold-start guard is unchanged; this covers deep navigation.
- `tsc --noEmit` clean; lint clean on changed files (pre-existing warnings untouched).

---

### 2026-07-27 — Courses screens wired (list + create + join-by-code)

- **`courses.tsx`** — dropped the mock `TERMS` array. New `fetchMyCourses()` in
  `lib/courses.ts` (typed `MyCourse`, reads `GET /api/courses`). Courses grouped by
  `term_label`, null labels collapsed into one "Your courses" bucket (first-seen order
  preserved). Real `ActivityIndicator` loading + "No courses yet — join or create one
  below" empty state. Each row now routes to `/topics` **with the course id as a param**
  (`router.push({ pathname: '/topics', params: { courseId } })`) so topics wiring later
  doesn't lose it. Switched the mount fetch to **`useFocusEffect`** so returning from the
  create/join modals shows fresh data (backend already busts the course-list cache on
  create/join).
- **Mis-route fixed:** footer "Join with a code" was `→ router.push('/topics')`; now opens
  the new `/coursejoin` modal. "Create a course" (`/coursecreate`) and "Discover"
  (`/discovery`) were already correct, left as-is.
- **`coursecreate.tsx`** — replaced the whole mock (MATCHES array, name-only form, both
  mis-routed links) by **reusing `<CourseAcquisition/>`** inside a modal shell (✕ →
  `router.back()`). That component already does cohort→create→proximity→invite, requires
  both code+name, force-creates on "Make my own anyway", joins a near-match on "Join this
  one", and shares the invite via native `Share`. Single source of truth for the flow now.
- **`coursejoin.tsx` (NEW)** — `presentation:'modal'`, registered in `_layout.tsx`. One
  invite-code `Input` → `joinCourse({inviteCode})` (`POST /api/courses/join`) → `router.back()`
  to the course list (which refetches on focus). Emergent-set model respected: join only via
  the join endpoint, no public browse.
- **Verify:** `npx tsc --noEmit` clean; `eslint` clean on all changed files
  (`courses.tsx`, `coursecreate.tsx`, `coursejoin.tsx`, `lib/courses.ts`, `_layout.tsx`).
  Pre-existing `onboarding.tsx`/`testbuilder.tsx` lint errors left untouched.
  **Not yet run on a device/simulator** — owner runs the dev build.

### 2026-07-27 — Topics screen wired (course detail + topic list)

- **`topics.tsx`** — dropped the mock `TOPICS` array. Reads `courseId` via
  `useLocalSearchParams` (the param `courses.tsx` now passes), fetches
  `GET /api/courses/{id}` through new `fetchCourseTopics()` in `lib/topics.ts` (typed
  `CourseDetail`/`CourseTopic`) — one enrollment-checked call gives the course name/code
  header **and** the ordered topic list. `useFocusEffect` so returning from the capture
  modal refreshes. Real `ActivityIndicator` loading, "No topics yet…" empty state, and an
  error line (incl. a "No course selected" guard when the param is missing).
- **Routing chain preserved:** topic rows → `/note` with `{ topicId, courseId }`; "Add
  material to this course" → `/capture` with `{ courseId }` (disabled if no courseId). Note
  and capture are later queue items — the ids are carried forward, not consumed yet.
- **Drift flagged (not faked):** the mock showed a per-topic status badge
  (ready/synthesizing/empty) + resource count. No list endpoint carries those —
  `knowledge_status`/`resource` state is only on `GET /api/topics/{id}`, and the backend
  deliberately avoids embedding it in lists (N+1). Per §1 ("flag drift rather than invent
  backend behavior"), I dropped the badge/count and used a real subtitle (description →
  `Week N` → "No description yet"). If we want status in the list, that's a backend change
  (embed `knowledge_status` + a resource count in the topics payload) — escalate before
  building.
- **Verify:** `tsc --noEmit` clean; `eslint` clean on `topics.tsx` + `lib/topics.ts`.
  Not yet run on a device/simulator (owner runs the dev build).

### 2026-07-27 — Capture wired with live WebSocket progress (+ first mobile WS client)

User decisions this pass: **live progress** (not fire-and-forget) and **files + photos**
(not files-only). Backend untouched — all four capture forks resolved on the mobile side.

- **New libs:**
  - `lib/cloudinary.ts` — direct unsigned-preset upload from the device (RN `FormData`
    with `{uri,name,type}`), mirroring `frontend/src/lib/cloudinaryUpload.ts`. Env:
    `EXPO_PUBLIC_CLOUDINARY_CLOUD_NAME` / `_UPLOAD_PRESET` (public by design).
  - `lib/filePicker.ts` — `pickDocuments` / `takePhoto` / `pickPhotos` over
    `expo-document-picker` + `expo-image-picker`, all normalised to `PickedFile`; cancelled
    picker → `[]`, denied permission → `PermissionDeniedError` (friendly message).
    `takePhoto` **bursts** — camera is single-shot per launch, so it re-opens after each
    photo and accumulates until the user cancels (multiple board/slide shots group together).
  - `lib/capture.ts` — `startCapture()` (`POST /api/courses/{id}/capture`) + the
    `CaptureEvent` union typed to match `capture_worker.py`'s `capture_progress` /
    `capture_complete` / `capture_failed` payloads.
  - `lib/courseSocket.ts` — the first mobile WS client (see §2.9). `API_BASE_URL` now
    exported from `lib/api.ts` so it can derive `ws(s)://…`.
- **`capture.tsx`** — full rewrite: source picker → `uploading` → `working` (live stage
  from WS) → `done` (filed topics + counts + "to check" flags) / `failed`. Reads `courseId`
  param (from topics). Subscribes to the room *before* the POST so no early event is missed;
  filters by `batch_id`; disconnects on complete/fail/unmount. "Back to course" → topics
  (refetch-on-focus surfaces the new topics).
- **Drift dropped (not faked):** no "confirm structure" step (worker auto-files, no confirm
  endpoint) and no "paste text" source (capture is files-only; text is a topic-level
  resource endpoint). Flagged per §1.
- **Verify:** `tsc --noEmit` clean; `eslint` clean on all new files (the one remaining lint
  line is a **pre-existing** `axios.create` warning in `api.ts`, not from this change). Not
  run on a device — needs the two owner actions in §2.5 (Cloudinary env vars + dev-client
  rebuild for the native pickers).

---

## 4. Known gaps / traps for whoever picks this up

- **`EXPO_PUBLIC_API_URL` defaults to `http://localhost:8000`** in `lib/api.ts`. On a
  physical phone via Expo Go, `localhost` resolves to the *phone*, not the Mac — see
  `docs/mobile-setup.md` §"Networking: phone ↔ Mac" for the LAN-IP fix before testing
  login on-device.
- **Google OAuth has no mobile UI on purpose** (§1). The backend flow
  (`GET /google` → `GET /google/callback` → `POST /oauth/register` for phone
  attachment) exists and is tested, but is not wired to a button anywhere in `mobile/`.
  Building the in-app browser / deep-link handler for it is post-launch work — see §5.
- **Test harness flakiness (pre-existing, not caused by this session's changes):** the
  session-scoped schema-rebuild fixture in `backend/tests/conftest.py` occasionally
  deadlocks on `TRUNCATE ... RESTART IDENTITY CASCADE` when the full suite is re-run
  back-to-back against the same live Postgres container shortly after a prior run (no
  `pytest-xdist` is installed, so it isn't worker contention — more likely leftover
  connections/locks). Not something to "fix" reflexively; if hit, wait a beat or reset
  the schema (`DROP SCHEMA public CASCADE; CREATE SCHEMA public;` on `notesos_test`
  only, never the dev DB) rather than assuming new code broke something.
- **`npx expo install <pkg>` fails under this sandbox** with `EALLOWSCRIPTS` (project-
  scoped installs can't use `--allow-scripts`). Use
  `npm install <pkg> --ignore-scripts` instead.
- **A separate, unrelated in-progress cleanup exists on this branch**: the user is
  independently removing the v1 `Test`/`TestQuestion`/`TestAttempt`/`TestAnswer` model
  in favor of `PracticeTest` (B14). `backend/app/models/test.py` is already deleted in
  the working tree; `models/__init__.py` and `services/progress.py` have partial edits
  from that separate effort. Don't "fix" this by restoring the old model — it's
  intentional, just uncommitted. If you hit a stale `ModuleNotFoundError` referencing
  `app.models.test`, it's bytecode cache, not a real import:
  `find backend -name "__pycache__" -type d -exec rm -rf {} +`.

---

## 5. Explicitly out of scope right now

Do not start these without the user raising them again:

- Redesigning the retrieval-mode picker UI (§1, parked).
- Any reports/moderation backend surface (§1, rejected).
- **Google sign-in on mobile.** Backend support already exists and is tested (§1) — the
  remaining work is purely mobile-side (in-app browser or deep-link handler for
  `GET /google` → `/google/callback` → `POST /oauth/register`). Not launch-scoped; pick
  up only if the user asks for it post-launch.
- Jumping ahead in the §2 queue to wire multiple unrelated screens in one pass — this is
  a step-by-step integration, not a batch rewrite of all 19 screens.

---

## 6. Epic: Onboarding social graph (contact-match + cohort discovery + invite)

> Status: **scoped, blocked on two decisions (6.3), not yet started.** Raised by the user
> 2026-07-26 while wiring onboarding. This replaces the mock "Pick from catalog" setup
> step. None of the backend for this exists yet.

### 6.1 The vision + the flow order (confirmed 2026-07-26)

Three surfaces. **Order matters** — the user reasoned through it: lead with the
zero-permission, zero-cost surface that *prevents duplicate course creation*, then earn
the heavier contacts-permission ask only after value is felt.

**Flow (locked):**

```text
school → profile
      ↓
1. COHORT (info-match, FIRST)  "Active courses in your school · year · semester" → join any
      ↓  (nothing relevant, or wants to add their own)
2. CREATE (fallback only)  → proximity check catches near-dupes → invite
      ↓
   → home  (value delivered)
      ↓
3. CONTACTS (Snapchat-style, LAST — after value)  "See who you know on NotesOS"
   → contacts permission → join your contacts' courses + invite the rest
```

1. **Cohort / info-match discovery — FIRST.** Use the user's own signals (school +
   program + entry_year) to surface matching **active** courses: *"3 active courses in
   your school, year and semester."* No permission needed; works immediately after
   profile. **This is the duplicate-create guard** — the user sees the course already
   exists and joins instead of forking a second one.
2. **Create — fallback only, never the first move.** Only when cohort surfaces nothing
   relevant. The proximity check is a second dupe guard at create time. (Leading with
   create was explicitly rejected: a user would build a course that already existed —
   "a waste of resources.")
3. **Contact-match discovery (Snapchat-style) — LAST, the final onboarding beat.** After
   value is felt: read phone contacts, cross-check against our DB (matched on phone —
   *why* phone is the primary identity), return which contacts are on the platform **plus
   their courses** to join, and invite the rest. The heavier contacts-permission ask
   belongs here, not up front.

**Cold-start reality (accepted):** the *first* users at a brand-new school get an empty
cohort (nothing active yet) and no contacts on-platform — the flow degrades gracefully to
create → invite. Inherent to any emergent product; not a bug.

### 6.2 Gap analysis — what exists vs. what's missing

**Exists (backend):**

- `POST /api/courses` (proximity check: similar courses at your school by code/name +
  school/program/year signals — `find_course_candidates`).
- `POST /api/courses/join` (join by `invite_code` or `course_id`).
- `GET /api/discovery/classmates` + `/courses` — **enrollment-overlap only**, so empty for
  a brand-new user.
- Course create returns `invite_code` + `share_link`.
- Full terms CRUD at `/api/terms` (+ `/vocab`).
- **Phone is unique + indexed on `User`** — the join key contact-match needs.

**Missing (backend — all NEW):**

- `POST /api/discovery/contacts` — accept a batch of the user's contact phone numbers,
  return matched registered users (id, name, avatar) + their activity-gated courses,
  ranked (school-match first). **Privacy model is decision 6.3-A.**
- `GET /api/discovery/cohort` — active courses at the caller's school + program +
  entry_year (+ term?), activity-gated. **Reconciliation with the emergent-set model is
  decision 6.3-B.**
- (Maybe) an invite endpoint, or just reuse `invite_code`/`share_link` client-side.

**Missing (mobile — all NEW):**

- `expo-contacts` dependency + a contacts-permission flow (with a clear rationale screen;
  contacts are sensitive — permission must be explicit and skippable).
- Onboarding tail rework: profile → cohort/contact results → select courses to join →
  home; empty → create → contacts-permission → invite.
- An **invite UI** (share invite code / pick contacts to invite) — none exists today.
- Rework `discovery.tsx` (currently all mock), `coursecreate.tsx` (wire real create +
  proximity offer + add an invite stage), and fix mis-routed footer links in
  `courses.tsx` ("Join with a code" → `/topics`) and `coursecreate.tsx`
  ("Make my own anyway" → `/capture`).
- (If cohort filters by semester) a **term/semester creation UI** — none exists today;
  backend is ready.

### 6.3 Decisions

- **6.3-B — Cohort discovery vs. the emergent-set model — DECIDED 2026-07-26.** Proceed:
  cohort discovery is **strictly scoped to the caller's own school + program + entry_year**
  (never a global browse) **and keeps the activity gate** (only courses past `ACTIVITY_MIN_*`
  surface). This is the surface being built first. Note: "semester" is not a shared,
  structured attribute (Terms are per-user personal labels), so v1 cohort matches on
  school + program + entry_year; semester is a possible later refinement, not in v1.
- **6.3-A — Contact-upload privacy model (PII-sensitive) — STILL OPEN, deferred.** Contact-
  match is now the LAST beat (§6.1), so this is settled when that piece is built, not now.
  Recommended default when we get there:
  the **client SHA-256-hashes each normalized phone number** and uploads only hashes;
  the server matches against hashes of registered phones and returns matches only,
  **persisting nothing about non-users**. This avoids handing the server a plaintext
  social graph of people who never signed up. Caveat to accept: phone-number hashes are
  brute-forceable (small input space), so this is "don't store a plaintext non-user
  graph," not strong private-set-intersection — acceptable for launch, documented as a
  known limitation. Alternative: upload raw normalized numbers, match, discard (simpler,
  but the request carries plaintext PII).

### 6.4 Build order (6.3-B settled; contact-match's 6.3-A settled when we reach it)

1. **Backend, TDD** (tests vs. real Postgres): `GET /api/discovery/cohort` — school +
   program + entry_year scoped, activity-gated. ✅ **DONE 2026-07-26** — `get_cohort_courses`
   in `services/discovery.py`, endpoint in `api/discovery.py`, 10 tests in
   `tests/test_discovery_cohort.py` (31 green across cohort+discovery+proximity+courses+enrollment).
2. **Mobile onboarding tail:** cohort results → select-to-join; then the empty→create→
   invite fallback. ✅ **DONE 2026-07-26** — `lib/courses.ts` (typed
   fetchCohort/joinCourse/createCourse), `components/onboarding/CourseAcquisition.tsx`
   (cohort→create→invite stages, incl. proximity offer + native Share invite), and
   `onboarding.tsx` reworked (STEPS now school→profile→courses→done; mock catalog/code
   setup step removed). `tsc --noEmit` clean. **Not yet run on a device/simulator** —
   needs a live backend + `EXPO_PUBLIC_API_URL` pointed at it (see §4).
3. **Invite UI** — partially covered: onboarding's invite stage shares the created
   course's `invite_code`/`share_link` via native Share. A richer standalone invite
   screen (pick contacts) is still open and folds into step 4.
4. **Contact-match** (backend `POST /api/discovery/contacts` per 6.3-A, then mobile
   `expo-contacts` + the "who you know" final beat).
   - **Backend ✅ DONE 2026-07-27.** `phone_hash` column on `User` (indexed, nullable;
     populated at register + oauth-attach, backfilled on login); canonicalisation via
     Google libphonenumber (`services/phone.py`, `phonenumbers` dep added to
     requirements) with a mirrored fallback; `match_contacts` + `POST /api/discovery/contacts`
     (upload hashes only, returns matched users + activity-gated same-school courses,
     same-school ranked first, capped at 2000 hashes). 15 tests
     (`test_phone.py` + `test_discovery_contacts.py`); 63 green across the touched suites.
     **⚠️ Owner action: run `alembic revision --autogenerate -m "user phone_hash"` +
     `alembic upgrade head`** (models changed; tests build schema from metadata so they
     don't need it, but the dev/prod DBs do). Existing rows backfill lazily on next login.
   - **Mobile ✅ DONE 2026-07-27.** Deps `expo-contacts`, `expo-crypto`, `expo-localization`,
     `libphonenumber-js` (all resolved to SDK-57-aligned versions via npm; the three
     expo-* modules are native → **owner must rebuild the dev client** before this runs).
     `mobile/src/lib/phone.ts` mirrors `services/phone.py` canonicalisation (libphonenumber
     → E.164 + digit-strip fallback); **device-region aware, not NG-hardcoded** (see §6.5)
     so it works globally. `mobile/src/lib/contacts.ts` (permission + read address book +
     dedupe-on-canonical + local SHA-256 hash + `POST /api/discovery/contacts`; raw numbers
     never leave the device). `mobile/src/app/contacts.tsx` — the "See who you know on
     NotesOS" screen: explicit permission rationale, matched contacts → join their courses,
     invite-the-rest via native Share; skippable at every stage. Wired as the final
     onboarding beat: `onboarding.tsx` "done" step → `/contacts` (or skip → `/home`);
     registered in `_layout.tsx` (nav FAB hidden, like `/onboarding`). `app.json` gains the
     `expo-contacts` config plugin with `NSContactsUsageDescription`. `tsc --noEmit` clean,
     lint clean on the new files. **Not yet run on a device** — needs the dev-client rebuild
     and the `phone_hash` migration (below) applied to the backend it points at.
5. **Terms/semester creation UI** — deferred; not a v1 cohort dependency (§6.3-B).

### 6.5 Phone canonicalisation note (why not plain E.164 everywhere)

Contact-match only works if the device and server produce the **same** canonical string
for the same number. We use Google's libphonenumber on both sides — `phonenumbers`
(server) and `libphonenumber-js` (client, `mobile/src/lib/phone.ts`, shipped 2026-07-27) —
both ports of the same library, so valid numbers agree on E.164. For the rare unparseable
input a tiny digit-strip fallback is mirrored in both files so hashing stays total.

**Global, not NG-only (the region seam).** The product launches in Nigeria but must work
everywhere. National-format numbers need a *default region* to interpret; the client uses
the **device's own region** (`expo-localization` `getLocales()[0].regionCode`), falling
back to `NG` only when the OS reports nothing — so a US user's `(415) …` and a Nigerian
user's `0803 …` both canonicalise correctly from the same address book. International
`+…` numbers carry their own country code and ignore the region on both sides. The
server's `DEFAULT_PHONE_REGION` (`NG`) only interprets a registering user's *own* phone
when they type it in national format — the one caveat: a non-NG user who registers in bare
national format (no `+`) would be canonicalised against NG. Documented limitation; register
in international format (or from the launch market) and it's exact. Multi-region hardening
later = confirm both libphonenumber ports still agree; the seam is already there.

Each ships behind tests and one screen/flow at a time, per the top-of-doc rule.
