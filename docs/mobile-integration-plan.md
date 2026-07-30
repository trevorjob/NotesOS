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
> Last updated: 2026-07-29. Branch: `v2`.

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

### 2.3 Courses ✅ (wired 2026-07-27; navigation/IA reworked 2026-07-28)

- [x] `courses.tsx` — list/read from `api/courses.py` (`fetchMyCourses()`), grouped by
  `term_label` (null → "Your courses"), real loading/empty states, refetch-on-focus.
  **Reworked to an accordion 2026-07-28** (see the IA-rework log entry): tap a course →
  topics expand inline (each → its note); expanded also shows "+ Add material" and, when the
  course has no topics, "set up from your syllabus" (→ `/capture?mode=outline`). Mis-routed
  "Join with a code" (was `/topics`) → `/coursejoin`.
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

### 2.5 Topics & resources ✅ (wired 2026-07-27; topic-status badge is a tracked backend enhancement below)

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
- [x] **Outline scaffold (syllabus → topic skeleton)** — wired 2026-07-28. The *other*
  `api/capture.py` surface: `POST /api/courses/{id}/outline` (synchronous, no worker/WS).
  `scaffoldOutline()` in `lib/capture.ts` + reusable `components/capture/OutlineScaffold.tsx`
  (paste syllabus text and/or snap photos → uploaded to Cloudinary as `image_urls`,
  vision-transcribed server-side → LLM parses into empty labeled topics, deduped by title).
  **Two entry points, one component (user asked for both):** (a) inside the capture modal
  as an `intent` fork — `mode=outline` opens straight into it, and the dump's source list
  links across ("Set up topics from a syllabus instead" ↔ "Add material instead"); (b) the
  `topics.tsx` empty state's "Set up from your syllabus" button → `/capture?mode=outline`.
  **Why it matters:** the dump worker classifies into existing topics when the course has
  any, else cluster-guesses — so scaffolding first makes later dumps land in the right
  buckets. Note: the Next.js frontend never implemented this endpoint (it creates topics
  manually via `CreateTopicModal` → `POST /topics`), so there was no web pattern to mirror.
- [x] `source.tsx` — wired 2026-07-27. "Read the original" now lists a topic's raw
  resources from `GET /api/topics/{topic_id}/resources` via `fetchTopicResources()` in
  `lib/resources.ts`. Reads the `topicId` param, real loading/empty/error states,
  refetch-on-focus, expand-a-row → verbatim `content` (+ "Added by", + "Hard to read" when
  `needs_review`). Quarantine gate honoured: the server only returns a quarantined resource
  to its own uploader, so the "Held · only you" badge = `quarantined`. **Id-chain:**
  `note.tsx` (still mock, §2.6) got a one-line forward — it already receives
  `topicId`/`courseId` from topics, now passes them into `/source`.

### 2.6 Note / knowledge ✅ (wired 2026-07-28; backend concept-states endpoint added)

- [x] **Backend — `GET /api/topics/{id}/concept-states` (NEW, TDD).** The note's heat-map had
  no backend (`GET .../knowledge` returns the shared note but no per-user mastery). Added a
  per-user endpoint joining `Concept` ⋈ `ConceptState` (the note's `concepts[].term` maps 1:1
  to `Concept.text` via `sync_concepts`), returning `[{concept_id, term, definition, state,
  due, reps, lapses}]` + a `summary` count. State derived by new `derive_mastery()` in
  `services/retrieval/scheduler.py` (the FSRS-owning file): `new` (reps 0) → `shaky`
  (last_grade `again` or FSRS Relearning) → `fading` (due ≤ now) → `solid` (due in future).
  **Per-user, so never cached** (the shared note is cached separately). 10 tests
  (`test_knowledge_concept_states.py`: derivation edges, ordering, per-user isolation,
  enrollment 403, 404, empty topic); 38 green across concept-states + retrieval scheduler/api/
  concepts/engine, no regressions. **Owner: no migration** (no model change; `Concept`/
  `ConceptState` already existed).
- [x] `note.tsx` — wired 2026-07-28. Fetches its own header (`GET /api/topics/{id}` — callers
  only pass `topicId`/`courseId`, not the title) + `GET .../knowledge` + `GET .../concept-states`
  in parallel, `useFocusEffect`, real loading/error/empty/synthesizing/failed states.
  **Note body is markdown** (`react-native-marked` via the `useMarkdown` hook so it lives in
  the screen's own ScrollView, not a nested FlatList; `components/note/NoteMarkdown.tsx` wraps
  it in an error boundary → plain-text fallback). **The WHOLE note is lit by mastery, inline**
  (reworked 2026-07-29 — see below): a custom renderer (`makeRenderer` → overrides `Renderer.
  text()`) scans every text run for concept terms and wraps each in a tappable, mastery-coloured
  span; `LitText` does the same for key points; `buildConceptIndex` builds the matcher
  (`components/note/mastery.ts` holds the state→style map). Tap a lit term → retrieval sheet →
  `/retrieval` (id-chain `concept`/`conceptId`/`conceptState`/`topicId`/`courseId` forwarded;
  retrieval itself is §2.7). `lib/note.ts` is the typed client (`fetchTopicHeader`/
  `fetchTopicKnowledge`/`fetchConceptStates`/`regenerateKnowledge`).
  - **Restored 2026-07-29 (I over-trimmed these as "drift"; user caught it):**
    - **Topic pager** (prev/next buttons + dots) — back, now backed by real sibling topics
      (`fetchCourseTopics(courseId)`); prev/next `router.setParams({topicId})` cycles with
      wrap-around, dots track position, title/active-dot update instantly (course-scoped fetch,
      so the header doesn't flicker while paging). The ⌕ QuickSwitcher stays as the *global* jump.
    - **Course breadcrumb** — real course name (from the same call), not a hardcoded subject.
    - **Attribution layer (contribution-level) — built 2026-07-29, backend + mobile.** New
      `GET /api/topics/{id}/contributions` (per-user, uncached): distinct **contributors**
      (uploaders of non-quarantined resources), **recent** additions (last 3: who/what/when),
      and **new_since_last_read** (resources added after the caller's prior `NOTE_VIEW`; a 15s
      grace window drops the current open, since `record_consume` appends a view on every
      knowledge GET). Header shows a real attribution beat ("Ada added “Lecture 5” · 2d ago",
      or "N new since you last read"); footer "Built by Ada, Kofi & N others"; "Says who?"
      lists contributors. 8 TDD tests (`test_knowledge_contributions.py`), **no migration**.
    - **"Says who?" provenance sheet** — back with honest copy + the contributor list + a button
      into "Read the original". (The mock's section-level "Ada added the ETC *section*" attribution
      is the deferred richer version — would need the synthesizer to tag sections; user chose
      contribution-level for now.)
  - **Still drift (correctly gone):**
    - **Hardcoded typed sections** (stages / worked-example / table / rendered-math) — those
      are all *markdown content* now, rendered from `consolidated_note`, not typed props.
    - **"6 classmates built this note"** — replaced by the real contributor line above.
  - **Math rendering — DONE 2026-07-29 (real LaTeX).** Display math (`$$…$$`, `\[…\]`) splits
    out (`splitNoteSegments`) and renders as true MathJax SVG via `react-native-mathjax-svg`
    (uses the installed `react-native-svg` — **no WebView, no fonts, offline**), horizontally
    scrollable, own error-boundary → raw-LaTeX fallback (`MathBlock.tsx`). Inline math (`$…$`,
    `\(…\)`) → Unicode (`latex.ts` `texToUnicode`: greek, super/subscripts, operators, frac/
    sqrt) so it flows inside prose as lightable text — an SVG View can't sit mid-line in a
    wrapping RN `<Text>`, so inline stays text (complex inline degrades readably; a known
    limit). Converter unit-tested off-device (pure module). `components/note/latex.ts` +
    `MathBlock.tsx` + a `react-native-mathjax-svg` ambient d.ts.
    - **⚠️ Owner:** `react-native-mathjax-svg` added (pure-JS, bundles its own MathJax; peer
      `react-native-svg` already in `package.json`). If `react-native-svg` is already in your
      dev client (it has been in deps), this is a **JS-only reload, no rebuild**; if it was
      never built in, one rebuild picks up both.
  - **⚠️ Owner action:** `react-native-marked@^8.1.1` added (pure-JS; peer dep
    `react-native-svg` was already installed, so **no dev-client rebuild needed** for this one).
  - **Verify:** `tsc --noEmit` clean; `eslint` clean on `note.tsx` + `lib/note.ts` +
    `NoteMarkdown.tsx`. Not run on-device (owner runs the dev build).
  - **⚠️ Lighting depends on §2.7.** The heat-map is data-driven: mastery is written *only* by a
    completed `POST /api/retrieval/attempt`. Retrieval is still the mock screen, so the app has
    recorded **0 attempts** (dev DB 2026-07-28: 84 concepts, **0 concept_states**) — every
    concept is `new`/neutral and nothing lights until §2.7 records real attempts. The note is
    correct and armed; it lights as a side-effect of wiring retrieval. Zero-mastery UX hardened
    (per-concept marker dot — hollow → fills with colour as it lights — + an always-on hint) so a
    fresh note reads as "not started," not broken.

### 2.7 Retrieval / study loop 🟡

> **Retrieval is getting an experience redesign** (engine-chooses doorway, ambient across the
> app, session-as-flow) — scoped in [`retrieval-experience.md`](./retrieval-experience.md).
> The §1 parked "mode-picker" complaint is now reopened *with the user's direction*. Wiring
> below is the foundation the redesign builds on; the redesign itself is not started (see that
> doc's §10 build order).

- [x] `retrieval.tsx` — wired 2026-07-29 to `api/retrieval.py`. `lib/retrieval.ts` typed client
  (`fetchModes`/`nextChallenge`/`submitAttempt`/`revealSolution`/`recap*`/`dump*`). Full session:
  next → (confidence beat on posed modes) → attempt → real outcome + calibration + new FSRS
  schedule ("next review in N days"). Modes driven off `GET /modes` (quiz/pretest/ramble/teach)
  with recap/dump appended (topic-scoped, outside the registry). Layout preserved per §1. **This is
  what lights the note for real** — every completed `/attempt` writes ConceptState. See the log
  entry for the mode→shape map, the worked-STEM reveal flow, and what was deferred (voice, paper
  photo, keep-going, home hero).
- [ ] `testbuilder.tsx` — wire to `api/practice_test.py` (B14 authored practice test). This is a **distinct concept** from `retrieval.tsx`'s scheduled review — see `[[authored-practice-test]]` memory. Don't merge them. **Note:** the old mock timed-test (`?mode=test` → a hardcoded-question quiz in `retrieval.tsx`) was removed as fabricated data — testbuilder's `?mode=test` link now lands on an honest "coming soon" placeholder until this item wires it to `/api/practice-tests`.

### 2.8 Voice / audio ⬜

- [ ] `listen.tsx` / `voice.tsx` — wire to `api/voice.py` (WS `/ws/voice/{course_id}`). Confirm premium-lane gating before wiring (architecture docs flag this as a premium feature).

### 2.9 Notifications ⬜

- [ ] `notifications.tsx` — wire to `api/notifications.py`. Check whether WebSocket push (`services/websocket.py`) or polling is the intended pattern for mobile (mobile can't rely on the same browser WS assumptions as the Next.js frontend — verify reconnect-on-background behavior).
- **Foundation landed 2026-07-27:** `lib/courseSocket.ts` — a minimal course-room WS client
  (`WS /ws/{course_id}?token=`, heartbeat, backoff reconnect, 1008=auth-stop), built for
  capture's live progress. It's the seed for this section. Still TODO for full §2.9:
  **reconnect-on-background** (AppState-aware — RN backgrounding drops the socket) and the
  user-scoped `/ws/user/{user_id}` channel for personal notifications.

### 2.10 Settings / profile ✅ (wired 2026-07-28)

- [x] Sign-out — wired under §2.1, lives on this screen
- [x] `settings.tsx` — wired 2026-07-28. Hydrates on mount from `GET /api/auth/me` +
  `GET /api/notifications/preferences` (`lib/profile.ts`, `lib/notifications.ts`); real
  loading/error states. **Tutor personality** (tone / explanation-style chips + "Use emoji"
  toggle) → `PATCH /me/personality`; chips carry backend slugs (lowercase), emoji maps to
  the `emoji_usage` **string** (`moderate`/`none`, not a bool). **Daily decay digest** →
  `PATCH /api/notifications/preferences` (`digest_enabled`) — its real home is the
  `notification_preferences` table, NOT the generic `/me/preferences` dict, so that's where
  it's wired. **Name** editable inline → `PATCH /me`; **phone** shown read-only (primary
  identity, not editable). **Change password** inline form → `POST /me/change-password`
  (8-char client guard + surfaces the server's "current password is incorrect"). All
  personality/digest saves are optimistic with per-control rollback on failure.
  - **Drift (both flagged, not faked):** (1) **"Night Journal"** (dark mode) removed — it's
    a theme concern needing `ThemeProvider` wiring + persistence, no clean `/me` field;
    revisit as a theming task. (2) **"Delete account"** removed — **no backend endpoint
    exists** (`api/auth.py` has no delete-account route); a red button that half-deletes is
    worse than none (Google-button precedent). Add the endpoint first if we want it.
  - **Note:** `/me/preferences` (the generic `preferences` dict + `personality_tags`) has no
    field in this mock, **and nothing in the backend consumes those columns** — they're
    write/read-only via `PATCH /me/preferences` with no service/worker/tutor reading them
    (traced 2026-07-28). Dead storage for now; `study_personality` and
    `notification_preferences` are the fields that actually drive behaviour. So `/me/preferences`
    is intentionally not called from settings.
- [x] **Delete account — soft-delete + anonymise (user chose this policy 2026-07-28).**
  Backend: new `POST /api/auth/me/delete` (`DeleteAccountRequest{password}`) — reauth for
  password accounts, then wipe PII (email/phone_hash/password/avatar/google_id/university/
  program/entry_year/personality/preferences/reset-token → null; `full_name` → "Former
  member"), set the `NOT NULL`+unique `phone` to a `deleted:{token}` sentinel (**frees the
  real number for re-registration**), `is_active=False`, and revoke all `RefreshToken`s.
  **Uploaded resources are kept** so classmates' shared notes don't break (they show
  "Former member"). Added an `is_active` gate to `get_current_user` (kills the ≤15-min
  access token instantly), `refresh`, and `login`. No model change (`is_active` already
  existed). 4 new tests in `test_auth.py` (reauth required, lock-out + token revoke, phone
  freed, PII anonymised); **44 green** across auth+user_signals+discovery_contacts+
  practice_test, no regressions. Mobile: `deleteAccount()` in `lib/profile.ts` + a
  destructive inline confirm in `settings.tsx` (warning + password → endpoint →
  `clearTokens()` → `/login`).

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

### 2026-07-27 — Phone input: explicit country picker (fix `+234 → +44` mangling)

- **Bug the user hit:** login "sent me +44…" for a Nigerian number. Cause: the earlier
  client canonicalisation guessed the region from the *device* locale (GB), and a national
  `0813…` is *also* a valid GB number, so libphonenumber rewrote it `+44…`. Guessing the
  region for the user's OWN number is fundamentally wrong.
- **Fix (user call: *"let the user provide their own intl codes"*):** explicit country
  picker, nothing guessed. New `components/ui/PhoneInput.tsx` (flag + dial-code button →
  searchable full-country modal, national-number field), `lib/countries.ts` (245 countries,
  names baked at build time — Hermes has no `Intl.DisplayNames`; regen script in §6.5),
  and `composeE164(country, national)` in `lib/phone.ts` (parses against the *chosen*
  country; a typed `+…` overrides the picker). `login.tsx` swapped its phone `Input` for
  `PhoneInput`; device region only pre-selects the country. Verified: `NG` + `08131234567`
  → `+2348131234567` (was `+44…`). Closes the §6.5 "register in international format" caveat.
- **Local auth (biometrics): user asked, answer = skip for launch.** Phone+password + the
  SecureStore session is enough; biometric unlock is a post-launch convenience (tracked §5).
- `contacts.ts` canonicalisation is unchanged — device region is *correct* for the address
  book (see §6.5). `tsc` + lint clean on all new/changed files. Not run on a device.

### 2026-07-27 — Source screen wired ("Read the original") + capture native-permission fix

- **`source.tsx`** — dropped the mock `RESOURCES`. New `fetchTopicResources()` in
  `lib/resources.ts` (typed `TopicResource`) reads `GET /api/topics/{topic_id}/resources`.
  Reads the `topicId` param, real loading/empty/error states, `useFocusEffect`, accordion
  rows → verbatim `content` with an "Added by {uploader}" line and a "Hard to read" note
  when `needs_review`. The Merge-Agent quarantine gate is server-side (a quarantined
  resource only ever comes back to its own uploader), so "Held · only you" = `quarantined`
  with no client logic. `note.tsx` (still mock) got a one-line id-forward into `/source`.
  Completes §2.5.
- **Capture native-permission crash fixed.** On-device capture crashed with missing
  `NSCameraUsageDescription`/`NSPhotoLibraryUsageDescription`. Root cause: `ios/` is a
  gitignored CNG artifact whose `Info.plist` was generated before the `expo-image-picker`
  plugin was added, so it only had the contacts key. The `app.json` plugin config was
  correct (`cameraPermission`/`photosPermission` → the NS* keys); it just needed a
  regenerate. Ran `npx expo prebuild -p ios --no-install`; `Info.plist` now carries all
  three usage-description keys. **Owner:** rebuild with a pod install (`npx expo run:ios`)
  since `--no-install` skipped CocoaPods. (Owner had already set the `EXPO_PUBLIC_CLOUDINARY_*`
  env vars — visible in `.env` during prebuild.) General rule reinforced: any `app.json`
  native/permission/plugin change needs prebuild + rebuild to take effect.
- **Verify:** `tsc --noEmit` clean; `eslint` clean on `source.tsx` + `lib/resources.ts`
  (the note.tsx `space` warning is pre-existing, confirmed via stash). Not run on-device.

### 2026-07-28 — Outline scaffold wired (syllabus → topic skeleton, two entry points)

- **Context:** the Next.js frontend **never calls** `POST /courses/{id}/outline` (grep-
  confirmed — it builds topics manually via `CreateTopicModal`/`POST /topics`). So this is a
  v2 backend capability with no web UI to mirror; mobile is the first client for it.
- **New:** `scaffoldOutline()` in `lib/capture.ts` (→ `{created, skipped}`) and reusable
  `components/capture/OutlineScaffold.tsx` — a multiline paste field + "Snap syllabus" /
  "Choose photos" (reusing `filePicker` + `uploadFilesToCloudinary`, folder
  `notesos/{courseId}/outline`). Submit → optional photo upload → `POST /outline` → result
  view ("Topics set up" / "N already existed"). Synchronous; **no WebSocket** (unlike the
  dump).
- **Both entry points share the one component** (user: *"inside capture and on empty state
  on a topics page — add from both"*): `capture.tsx` gained an `intent` state
  (`dump`|`outline`) seeded from a `mode` param, with cross-links each way; `topics.tsx`
  empty state got a "Set up from your syllabus" button → `/capture?mode=outline`.
- **Interaction with the dump:** seeding topics first = the dump worker *classifies* files
  into named buckets instead of cluster-guessing (it branches on "course has any topics").
  Scaffold→dump is the intended happy path.
- **Verify:** `tsc --noEmit` clean; `eslint` clean on all changed files. Not run on-device
  (same two owner actions as the dump: Cloudinary env vars — already set — + dev-client
  rebuild for the native pickers).

### 2026-07-28 — Settings wired (personality, digest, name, change-password)

- **`settings.tsx`** — dropped all mock local-only state. New `lib/profile.ts` (`fetchMe`,
  `updatePersonality`, `updateProfile`, `changePassword`) + `lib/notifications.ts`
  (`fetch`/`updateNotificationPreferences`). Hydrates from `GET /me` +
  `GET /notifications/preferences` on mount; loading/error states. Personality chips
  (tone/style) + emoji toggle → `PATCH /me/personality`; digest toggle →
  `PATCH /notifications/preferences`; inline name edit → `PATCH /me`; inline change-password
  → `POST /me/change-password`. Optimistic saves with per-control rollback.
- **Backend mapping gotchas worth remembering:** `emoji_usage` is a **string**
  (`moderate`/`none`), not a bool; the digest lives in the `notification_preferences` table
  (`digest_enabled`), **not** `/me/preferences`; `GET /me` does **not** return the generic
  `preferences` dict, so anything stored there can't be hydrated from `/me` (didn't need it
  here).
- **Drift removed + flagged:** Night Journal (dark mode → a theme task, deferred) and Delete
  account (**no backend endpoint** — needs one built first). Both dropped rather than shipped
  as dead controls.
- **Verify:** `tsc --noEmit` clean; `eslint` clean on the three changed files. Not run
  on-device.

### 2026-07-28 — Delete account (soft-delete + anonymise) — backend + mobile

First backend change of this integration effort (user: *"we definitely need delete acct
functionality"*; chose soft-delete over hard-delete to protect communal notes).

- **Backend (`api/auth.py`):** `POST /me/delete` anonymises PII, frees the phone (unique
  `deleted:{token}` sentinel), `is_active=False`, revokes all refresh tokens; keeps uploaded
  resources ("Former member"). Password reauth required. `is_active` gates added to
  `get_current_user` (kills the live access token), `refresh`, and `login`. `is_active`
  already existed on the model → **no migration**. `import update` added.
- **Tests:** 4 new (`test_auth.py`) — wrong-password rejected + account survives; lock-out
  (old access token → 401) + refresh revoked; phone freed for re-registration; PII wiped +
  deactivated (DB introspection). Ran `TEST_DATABASE_URL=…@localhost:5432/notesos_test`
  (note: conftest default password `blessed` didn't match the docker container's
  `notesos_dev_password` — set `TEST_DATABASE_URL` explicitly to run the suite). 44 green
  across the touched suites.
- **Mobile:** `deleteAccount()` in `lib/profile.ts`; destructive inline confirm in
  `settings.tsx` (warning copy + password field → endpoint → `clearTokens()` → `/login`).
  `tsc`/`eslint` clean.
- **Trap noted:** running backend tests needs `TEST_DATABASE_URL` pointed at
  `notesos_test` with the container's real password; the conftest default won't
  authenticate against the docker-compose Postgres.

### 2026-07-28 — Soft-deleted users made invisible to peers (delete follow-up)

User caught that anonymising ≠ hiding: a soft-deleted account was still enrolled, so it
leaked into classmate lists, discovery signals, and "N members" counts as "Former member".
Fixed the invariant **soft-deleted users are invisible to peers** in one place:

- **New `app/services/membership.py`** — `active_user_ids()` (subquery) + `active_member_counts()`;
  documents the rule so future enrollment queries don't re-derive it.
- **`discovery.py`** — `get_classmates` + `User.is_active`; `get_classmate_courses` classmate-id
  subquery filtered to active; `get_cohort_courses` peers filtered to active; all member counts
  now via `active_member_counts` (removed the local un-filtered `_member_counts`).
- **`proximity.py`** — member counts via `active_member_counts`; `_people_overlap` +
  `User.is_active`; `_classmate_overlap` classmate-ids filtered to active (removed local helper).
- **`courses.py`** — `list_courses` + `join_course` member counts are active-only.
- Contact-match already filtered `is_active` (and a deleted user's `phone_hash` is nulled) —
  untouched.
- **Tests:** 2 new in `test_discovery.py` (deleted classmate leaves the list; member_count drops
  2→1). 50 green across discovery/cohort/contacts/courses/enrollment/auth.
- **Known minor cache gap (not fixed):** the `/api/courses` list `member_count` is cached
  (`courses_list_key`); a *peer* deleting doesn't bust co-enrolled users' caches, so their count
  can read one high until TTL. Discovery/classmates are computed live (uncached), so those are
  correct immediately. Uploaded resources still show "Former member" as provenance (intentional —
  content is kept, identity anonymised).

### 2026-07-28 — Courses/notes navigation rework (IA — reach a note in ≤2 taps)

User: the add-to-course + course-browsing flow "is not at all intuitive" — Home "Add
material" went to `/capture` with no course (hit the guard, effectively broken), and a note
was 3 taps (courses → topics → note). Chose the **accordion** browse model. Deliberately a
multi-screen pass (one coherent flow, by request) — **all client-side**, no backend:
`GET /api/courses` already returns courses + embedded topics + `last_studied`.

- **QuickSwitcher wired to real data** (`components/nav/QuickSwitcher.tsx`, was 100% mock) —
  it's mounted on Home + every course/topic header, so ⌕ → tap a topic = its note is the
  **≤2-tap jump to any note from anywhere**. Flattens courses + topics into one searchable
  directory; "Recents" from `last_studied`; routes with real `topicId`/`courseId`.
- **`courses.tsx` → accordion** — tap a course expands its topics inline (no page change),
  tap a topic → note (2 taps while browsing). Expanded course also has "+ Add material"
  (→ `/capture?courseId`) and, when empty, "set up from your syllabus"
  (→ `/capture?courseId&mode=outline`). Term grouping kept.
- **Home "Add material" fixed** — was `/capture` with no course. Now opens a
  `CoursePickerSheet` (new reusable bottom sheet, `components/course/`) → pick → `/capture?courseId`.
- **Home recents wired** — "Jump back in" lists your recently-studied notes (from
  `last_studied`) as 1-tap links; removed the fabricated "2 classmates used your note" stat
  (no endpoint). Retrieval hero left as mock on purpose (that's §2.7, user's later task).
- **Verify:** `tsc` + `eslint` clean on all four changed files. Not run on-device.

### 2026-07-28 — Capture "did nothing" root cause: PDF force-OCR with tesseract missing

Report: uploaded a PDF, `POST /capture` returned 202, but "the worker never ran" and it
"returned an error." Traced end-to-end (all backend; mobile was fine):

- **Not a queue/Redis problem.** The `job:*` hashes were in the local redis with
  `status=completed`, `queue:capture:dead` empty. (`localhost:6379`'s `ssh` listener is
  **Colima's own port-forward** to the `notesos-redis` container — not a rogue tunnel; verify
  with `lsof -nP -iTCP:6379` → path contains `.colima`.) The user was watching the uvicorn
  terminal, not the `run_workers.py` one — the worker *did* run.
- **Real cause:** the job "completed" but created **0 resources**. `file_processor.extract_text_from_pdf`
  force-**OCR'd every PDF** (`pdf2image`→poppler, then `pytesseract`), and **tesseract isn't
  installed** here → extraction threw → the file was dropped → worker broadcast
  `capture_failed` and returned normally (so the job still marks `completed`). Debugging tell:
  **a "completed" capture with 0 attached resources = transcription failed.**
- **Fix:** `extract_text_from_pdf` is now **text-layer-first via `pypdf`** (pure-Python, no
  system binary), OCR only as a fallback for scanned PDFs. The exact failing PDF now yields
  3112 chars through the full worker path. `pypdf>=4.2.0` added to `requirements.txt`
  (**owner: `pip install -r requirements.txt`**). 23 capture tests green.
- **Types:** `.txt/.md` (decode), `.docx/.doc` (mammoth), images (GPT-vision), `.pdf` (now
  text-first) all work. **tesseract is now only needed for *scanned* PDFs** — optional;
  `brew install tesseract` if you want scanned-PDF OCR.

### 2026-07-28 — Note screen wired + note lit by mastery (new concept-states endpoint)

The §2.6 note surface — the wedge. User chose **"backend first, ship it lit"**: the note body
wired to existing `api/knowledge.py`, but the mastery heat-map (the note's signature per
`[[note-lit-by-mastery-kept]]` + system-spec §4/§5) had **no backend**, so that came first.

- **Backend (first change to `api/knowledge.py` this effort):** `GET /api/topics/{id}/
  concept-states` — per-user `Concept` ⋈ `ConceptState`, returns each concept's mastery
  `state` + a `summary`. `derive_mastery()` lives in `services/retrieval/scheduler.py` (the
  one FSRS-owning file): new → shaky → fading → solid. Per-user ⇒ uncached. 10 TDD tests, 38
  green across the touched suites, **no migration**.
- **Mobile:** `note.tsx` rewritten (3 parallel fetches: header + knowledge + concept-states),
  markdown body via `react-native-marked`'s `useMarkdown` hook (`NoteMarkdown.tsx`, error-
  boundary → plain-text fallback), key points list, **Concepts section lit by mastery** (tap →
  retrieval sheet → `/retrieval`, ids forwarded). `lib/note.ts` typed client. Full
  empty/synthesizing/failed/ready state machine off `knowledge.status` + `source_count`.
- **Drift dropped/flagged** (see §2.6): topic pager, hardcoded typed sections (now markdown),
  per-line "Says who?", "6 classmates built this" (→ honest "N sources"), freshness banner.
- **Two tracked follow-ups:** inline-lit terms *in prose* (v1 lights the Concepts section
  instead — robust vs. fragile find-and-wrap over markdown) and **LaTeX math rendering**
  (`react-native-marked` passes `$…$` through as text).
- **Owner:** `react-native-marked@^8.1.1` added — pure-JS, `react-native-svg` peer already
  present, so **no dev-client rebuild** for this. `tsc`/`eslint` clean; not run on-device.

### 2026-07-29 — Note lit INLINE (whole-note), Concepts section removed, seed for verification

Follow-up after the user saw the note on-device. Two things: (1) confirmed the lighting was
correct but invisible (0 attempts in the DB → all `new`); (2) design correction — **the whole
note lights up inline, not a separate Concepts section.** User: *"from the original designs its
the whole note that lights up not just the concepts section … if there's the words of the
concepts it should light up."* This is the spec's "active surface" (§4) — the words themselves
carry mastery, in the reading flow.

- **Inline lighting (the design's point).** A custom `react-native-marked` renderer overrides
  `Renderer.text()` (verified via the lib's Parser that plain/bold/heading/list text all route
  through `text()`), scanning each text run for concept terms (case-insensitive, longest-first,
  `\b`-bounded) and wrapping matches in a tappable, mastery-coloured `<Text>` span. `LitText`
  applies the same to key points. `buildConceptIndex` builds the matcher once (memoized) and is
  threaded into both. `new` terms get a faint dotted underline (still a live retrieval entry
  point); solid/fading/shaky get their colours. Recursion trap avoided by binding the original
  `text` before overriding. Non-string (already-composed) nodes pass straight through.
- **Concepts section deleted** (`ConceptsSection` gone) per the user — the note reads as one
  continuous surface again. Mastery style map extracted to `components/note/mastery.ts`.
- **Seed for immediate verification** (user asked to *see* it before wiring §2.7): 14
  `concept_states` rows (7 concepts × both `Trev` accounts) on topic *"Sources II: oral
  tradition"* — 3 solid, 2 fading, 2 shaky, 2 left `new`. Direct SQL, `ON CONFLICT` idempotent,
  `due` written as naive UTC to match the app. **Disposable** — delete when §2.7 makes mastery
  organically. (User confirmed the lit render works.)
- `tsc`/`eslint` clean on `note.tsx` + `NoteMarkdown.tsx` + `mastery.ts`. No backend change
  this pass.

### 2026-07-29 — Term-match hardening + full LaTeX math (SVG, no WebView)

Two follow-up asks after the inline-lighting pass.

- **Concept matching hardened.** Case-insensitive already (`gi`); added whitespace tolerance
  (term whitespace → `\s+`, so line-wrapped / double-spaced mentions match) and a shared
  `normalizeTerm` for both the lookup keys and each match. Trims terms before building the
  pattern. **Not** handled: morphological variants (plurals/tense) — needs stemming, risks
  over-matching; flagged.
- **Math rendering shipped (see §2.6).** User: *"we're building now … build the complete
  system so all students can use this."* So real LaTeX, not a stopgap: display math →
  MathJax-SVG (`react-native-mathjax-svg`, no WebView/fonts/network — uses the installed
  `react-native-svg`); inline math → Unicode so it flows and stays tappable. `react-native-
  marked` can't host a custom math token (its Parser's default case returns null), so math is
  split out *around* the markdown rather than tokenised inside it. Pure `latex.ts` converter
  unit-tested off-device. No math content exists in any note yet (0/14), so this is validated
  by construction + the converter tests until a STEM note is added.
- `tsc`/`eslint` clean across `note/` + `note.tsx`.

### 2026-07-29 — Restored note-page features I wrongly cut as "drift"

User: features from the original design were missing — "the navigation where u can go to the
next topic by clicking btns … and a few other missing things." I'd dropped them in the first
wiring pass calling them drift; that was over-trimming. Restored, each backed by real data (not
the mock's hardcoded arrays):

- **Topic pager** (prev/next + position dots) — `fetchCourseTopics(courseId)` gives the ordered
  sibling topics; prev/next `router.setParams({topicId})` cycles with wrap-around. Course-scoped
  fetch runs once per course (separate from the topic-scoped body load) so the header/pager don't
  flicker while paging, and the title updates instantly from the sibling list.
- **Course-name breadcrumb**, **"Updated {relative}"** line (real `generated_at`), and the
  **"Says who?"** provenance sheet (honest source-count copy → "Read the original").
- Only the mock's *fabricated* bits stay gone (per-change attribution, contributor count).
- `tsc`/`eslint` clean. Reminder for future passes: mock UI that implies data we lack should be
  flagged, but interaction/navigation the design intends shouldn't be dropped for lack of an
  endpoint when the data to drive it already exists (sibling topics did).

### 2026-07-29 — Note attribution layer (contribution-level) + accordion note

- **Attribution** was a key wanted feature I'd under-built. User chose **contribution-level**
  (over section-level or contributors-only). Backend: `GET /api/topics/{id}/contributions`
  (knowledge.py) — contributors / recent additions / new-since-last-read, all from existing
  `Resource.uploaded_by` + `ConsumeEvent(NOTE_VIEW)`; 15s grace excludes the current open (views
  are appended on every knowledge GET). 8 TDD tests, no migration, no regressions (18 green with
  concept-states). Mobile: `fetchTopicContributions` + `TopicContributions` in `lib/note.ts`;
  header attribution beat, "Built by …" footer, contributor list in "Says who?". Fetched
  non-fatally (`.catch(()=>null)`) so it never blocks the note.
- **Section-level attribution** ("Ada added the ETC *section*") is the deferred richer version —
  needs the synthesizer to tag note sections with their source resource/uploader. Not built.
- **Collapse default**: user's "everything open, all together" was the **QuickSwitcher** (⌕),
  not the browse page (`courses.tsx` is already a default-closed accordion). The switcher's idle
  view dumped a flat "All courses & topics" list (every topic expanded). Reworked to mirror the
  browse accordion: idle = Recents + **collapsed** course rows (tap → reveal topics inline → note);
  only a typed query shows the flat cross-course/topic results. Reset-on-close moved out of the
  open-effect (was a synchronous-setState-in-effect lint error) into a `close()` wrapper. Also
  added a **Cancel** button — the full-screen panel covered the tap-to-dismiss scrim, so there was
  no way out without selecting an item.
- `tsc`/`eslint` clean across `note.tsx` + `lib/note.ts`.

### 2026-07-30 — Retrieval: course-page scoped "study now" + voice Info.plist fix (redesign complete)

[`retrieval-experience.md`](./retrieval-experience.md) §11 step 6 — the last step. **The retrieval
experience redesign is now complete** (all six steps).

- **`topics.tsx` — course-scoped "Study now" card.** `fetchNextAction({ course_id })` drives a
  highlighted card at the top of the course page (topic + warm `reason` + est_minutes); one tap
  launches retrieval on the engine's pick for *this* course. Hidden when nothing's due. Same launch
  contract as the home hero + FAB. `tsc`/`eslint` clean.
- **Voice crash fixed (owner had rebuilt + hit it):** tapping 🎤 crashed with
  `NSSpeechRecognitionUsageDescription` missing — the **same stale-CNG-Info.plist gap as the 07-27
  camera fix**: `ios/` is a gitignored prebuild artifact generated *before* the speech-recognition
  plugin was added to `app.json`. Ran `npx expo prebuild -p ios --no-install`; `Info.plist` now
  carries `NSSpeechRecognitionUsageDescription` + `NSMicrophoneUsageDescription` (verified via
  `plutil`), alongside the existing camera/contacts keys. **Owner: rebuild with pods
  (`npx expo run:ios`)** since `--no-install` skipped CocoaPods. General rule (again): any
  `app.json` native/permission/plugin change needs a prebuild + rebuild to take effect.
- **Noted, not built:** *social-sciences subject family* — the backend `SubjectFamily` is only
  STEM/LANGUAGE/HUMANITIES/GENERAL, so social-sciences topics classify as GENERAL/HUMANITIES today.
  A dedicated family is a backend taxonomy change (enum + subject profile + classifier prompt) — its
  own item if wanted, not blocking.
- **Redesign status:** ✅ warm close · ✅ session flow · ✅ per-mode (STEM/paper/voice) · ✅
  context-worthy picker · ✅ FAB doorway · ✅ course-page entry. Non-blocking polish tracked in the
  design doc (cross-restart FAB persistence, affinity chips in the FAB menu, optional worked-photo).

### 2026-07-30 — Retrieval: the FAB reborn as the "study now" doorway (draggable, engine-picks)

[`retrieval-experience.md`](./retrieval-experience.md) §11 step 5. The global `NavFab` **was** the
exact flat-list problem the user complained about — and worse, it routed `/retrieval?mode=X` with
**no topic/concept**, which now hits the "open a note first" guard (i.e. it was broken against the
real backend). Rebuilt as the engine-chooses doorway (design §4).

- **Tap = study now** — `GET /next-action` (global) → `/retrieval` with the engine's topic/concept/
  mode. Nothing due → `/courses`. This is the fast path: engine picks WHAT *and* HOW, one tap.
- **Long-press = the pick menu** — the next-action's warm `reason` as context, a prominent
  "▶ Start — {mode}", then **mode-override rows** (keep the engine's topic/concept, change only the
  mode), + **Home** (kept — the FAB is still the global nav affordance). Backdrop-dismiss.
- **Draggable** — `PanResponder` + `Animated` (RN core, **no new deps, no rebuild**): moves only
  past a 6px threshold so taps/long-press pass through; clamped on-screen on release; position
  persists across route changes via module state (cross-restart persistence = flagged follow-up,
  needs a storage dep).
- **Discoverability** — a one-time hint bubble ("Tap to study now · hold to choose how"), dismissed
  on first interaction (module-flagged so it doesn't nag every remount).
- **Cleanups** — dropped the phantom "Timed test" (testbuilder's, not a retrieval mode); hid the FAB
  on `/retrieval` itself (`_layout.tsx`) so it doesn't overlap the session UI.
- **Coexists** with the per-surface entries (home hero, note-tap) per the locked decision. `tsc`/
  `eslint` clean on `NavFab.tsx` + `_layout.tsx`. Not run on-device (drag/gesture feel needs the
  owner's device pass).
- **Next (doc §11 step 6, last):** scoped `next-action` entry on the course/topic page.

### 2026-07-30 — Retrieval: context-worthy mode picker (best-fit-first, ranked by subject)

[`retrieval-experience.md`](./retrieval-experience.md) §11 step 4. The parked §1 complaint was
that the picker is "just a list" — now it's ranked and recommends.

- **`fetchTopicProfile` in `lib/retrieval.ts`** → `GET /api/retrieval/topics/{id}/profile` (existing,
  enrollment-gated). One call gives the topic's `subject_family` + `mode_mix` (affinity 0..1 for all
  six modes — note brain dump keys as `brain_dump`, mapped client-side).
- **`ModePicker` reworked** in `retrieval.tsx`: modes are ordered **best-fit-first** by `mode_mix`,
  the top one is badged **"Best fit"** and outlined, and a "Ranked for this {STEM/humanities/
  language} topic" header sets the context. STEM ranks quiz/pretest up; humanities ranks
  ramble/teach up (the engine's own knob, surfaced instead of acted on). Best-effort — falls back to
  the default order if the profile can't load; sheet layout otherwise unchanged.
- **No backend change** — reuses the existing profile endpoint. `tsc`/`eslint` clean on
  `retrieval.tsx` + `lib/retrieval.ts`. Not run on-device.
- **Next (doc §11 step 5):** the draggable FAB — global "study now" (default = `next-action`,
  long-press/caret = this picker), then step 6 (course-page scoped entry).

### 2026-07-30 — Retrieval: voice-answer input (on-device STT) across every written mode

[`retrieval-experience.md`](./retrieval-experience.md) §11 step 3, the second shared input surface.
**Clarified with the user: voice input is NOT premium** — the premium lane is *generated audio*
(listen mode), a separate later integration. So voice answering ships freely.

- **`useVoiceDictation` hook + "🎤 Speak" button** in `WrittenAnswer` (`components/retrieval/`).
  Speech is transcribed **on-device** via `expo-speech-recognition` (offline, free, live partial
  results) and streams into the editable answer field — same edit-before-grade confirm as paper.
  Available in every written mode (dump/recap/ramble/teach/quiz-short). Submits as plain text (the
  grader's voice-leniency is challenge-driven, so no per-attempt marker).
- **On-device vs server Whisper — a real fork the user raised.** Chose on-device: live partial
  results (big for rambling), offline, free, private; the editable confirm step covers OS-STT's
  weaker jargon accuracy. **I had drafted a server-Whisper endpoint** (`/transcribe-voice` +
  `transcription_service.transcribe_bytes` + tests) earlier this turn and **fully reverted it** when
  the user chose on-device — no dead backend left (grep-clean; 22 retrieval tests green).
- **Owner actions:** new dep `expo-speech-recognition` (native) + its config-plugin added to
  `app.json` (mic + speech-recognition usage strings) → **prebuild + rebuild the dev client** (same
  rebuild that picks up the image-picker). Accuracy varies by OS.
- **Verify:** `tsc`/`eslint` clean on `WrittenAnswer.tsx`, `useVoiceDictation.ts`, `retrieval.tsx`,
  `lib/retrieval.ts`. Not run on-device.
- **Net:** with STEM + paper + voice done, the written/STEM mode interfaces are substantially
  complete. Next is the context-worthy picker (doc §11 step 4).

### 2026-07-30 — Retrieval: paper-input surface (B8) wired into every written mode

[`retrieval-experience.md`](./retrieval-experience.md) §11 step 3, the shared input surface. The
paper substrate is "any written answer, in any mode can be a photo of handwriting" (system-spec
§5), so it went in as one reusable component and lit up all the written modes at once.

- **`components/retrieval/WrittenAnswer.tsx`** (NEW) — Textarea + "✎ Snap a photo of your
  handwriting". The photo is transcribed server-side and **drops into the editable field**, so
  correcting the text *is* the confirm step the substrate promises (grade what the student
  confirms, never the raw OCR guess). Shows the model's uncertainty as a check-hint
  (`has_illegible`/`has_uncertain`).
- **`transcribePaper` in `lib/retrieval.ts`** — `POST /api/retrieval/transcribe` (multipart).
  Uses raw `fetch` + a manual JWT header (not the axios instance): SDK-57's winter `FormData`
  needs Blob-compatible `expo-file-system` `File` parts, the same constraint `lib/cloudinary.ts`
  hit. Reuses `takePhoto` (burst, multi-page) from `lib/filePicker.ts`; camera/photo perms already
  shipped with capture, so **no new native config**.
- **Wired into every written mode** — dump, recap, ramble, teach, and quiz short/essay all use
  `WrittenAnswer`; submits carry `answer_origin:"paper"` (plumbed server-side through `/attempt`
  and the recap/dump grader — verified). Photos are ephemeral (never stored). **No backend change**
  — `/transcribe` (B8) already existed and is tested.
- **This also advances dump/ramble/teach** (their handwritten-input half is done); the remaining
  per-mode work for them is **voice** (§2.8, `/ws/voice`) — premium-gated, deferred until the lane
  is confirmed.
- **Verify:** `tsc`/`eslint` clean on `retrieval.tsx` + `lib/retrieval.ts` + `WrittenAnswer.tsx`.
  Not run on-device (owner runs the dev build; `/transcribe` needs the OpenAI vision key set).

### 2026-07-30 — Retrieval redesign: per-mode interfaces begin with STEM (worked)

[`retrieval-experience.md`](./retrieval-experience.md) §11 step 3, first mode. The generic renderer
gave every mode the same shape; STEM/worked is the most distinct, so it went first.

- **`components/retrieval/MathText.tsx`** (NEW) — renders a string that mixes prose + inline math
  (`$…$`) + display math (`$$…$$`), reusing the note's pipeline (`MathBlock` SVG for display,
  `latex.ts` Unicode for inline). No new deps.
- **`retrieval.tsx` — worked/STEM interface.** Problem, revealed solution, and result feedback now
  render **math as math**. STEM framing: "work it out on paper," confidence-*before*-reveal copy
  (protects the B9 ordering), reveal → the 4 honest self-grade buttons → a self-graded result
  headline (keyed off `outcome.detail.self_graded`, not a fake "/10"). Numeric STEM = a typed-number
  "Check". All other modes fall through unchanged. **No backend change** — the worked flow (`/next`
  worked → `/reveal` → self-grade `/attempt`) was already backed and tested.
- **Deferred (correctly):** the *optional* photo-of-work attachment (spec §5 — never required before
  self-grade; no attempt-image endpoint exists) folds into the paper-input surface built with
  dump/ramble.
- **Verify:** `tsc`/`eslint` clean on `retrieval.tsx` + `MathText.tsx` + `lib/retrieval.ts`. Not run
  on-device. **Owner note:** worked problems only appear on topics whose `subject_family` resolves
  to the self-calibration grading directive — set/override via `PATCH /api/retrieval/topics/{id}/profile`
  to see it on a given topic.
- **Next (doc §11 step 3):** ramble/teach/dump — these need the voice (§2.8) + paper (`/transcribe`)
  input surfaces, built with the first mode that needs them.

### 2026-07-30 — Retrieval redesign build starts: warm close (session flow + backend derive)

First build step of the retrieval experience redesign ([`retrieval-experience.md`](./retrieval-experience.md)
§11). Turns retrieval from one-shot into a **bout that ends with a warm close** (system-spec §5/§6).

- **Backend — `GET /api/retrieval/session-summary`** (`api/retrieval.py`) +
  `services/retrieval/session_summary.py`. Derives, over the user's most recent session (the same
  ≥15-min idle-gap clustering as `session.py` — refactored to expose `split_attempt_buckets` +
  `last_session_attempts`, DRY with `split_sessions`), what the bout changed: **firmed** (current
  mastery `solid`) vs. **slipping** (`shaky`/`fading`) concepts via the note's `derive_mastery`,
  plus the **calibration delta** (mean actual−predicted over attempts that carried a prediction,
  same ±0.15 band as `/attempt`). Uncached/per-user; enrollment-gated on `course_id`; `null` when
  there's no session. **No model change, no migration.** 10 tests (6 service in
  `test_session_summary.py` + 4 API in `test_retrieval_api.py`); 76 green across
  retrieval/session/recap/dump.
- **Mobile — session flow + warm close** in `retrieval.tsx`. "Keep going" now runs a real bout:
  it pulls the engine-selected **next due** concept (no `concept_id`), and an exhausted queue (404)
  is treated as the natural end, not an error → flows into the close. Result screen now offers
  **Keep going** + **Done for now**; "Done for now" (or exhaustion) → `CloseView`: growth-led
  headline ("You firmed up N concepts"), whispered slipping ("M still shaky — …"), a calibration
  line, and the recap-tomorrow hook. `fetchSessionSummary` + `SessionSummary` types in
  `lib/retrieval.ts`. Summary is best-effort (a plain "good push" close if it can't load).
- **Verify:** backend via `TEST_DATABASE_URL=…notesos_test`; mobile `tsc`/`eslint` clean on
  `retrieval.tsx` + `lib/retrieval.ts`. Not run on-device.
- **Next (doc §11 step 3):** per-mode interfaces — each mode gets its real experience (currently
  one generic renderer), coordinated with the voice (§2.8) + paper (`/transcribe`, B8) inputs.

### 2026-07-30 — Retrieval experience direction + home hero + labeled continuation

User reopened the parked retrieval-UX question (§1) with a clear direction: retrieval should
*live across the app*, engine-chooses by default, pick as the expand. Wrote the design doc and
landed the enabling wiring (the redesign itself — FAB, session flow, context-worthy picker — is
scoped but not built; see the doc's §10).

- **Design doc** — [`retrieval-experience.md`](./retrieval-experience.md): the doorway
  principle (engine-chooses / pick-as-expand, DECIDED), the per-surface map, FAB rework,
  session-as-flow + warm close, the context-worthy picker, backend support vs. gaps, and open
  decisions (§9) that need the user before the redesign builds.
- **Backend — `concept_text` on `POST /next`** (`api/retrieval.py`). `NextResponse` now carries
  the concept term (no model change, no migration — `Concept.text` already existed). Unblocks a
  labeled continuous session: each next challenge names its own concept instead of inheriting the
  one you started on. Test added to `test_retrieval_api.py` (happy-path asserts `concept_text`);
  13 retrieval-api tests green.
- **`retrieval.tsx` — "Keep going" restored** now that continuation is labeled correctly: after a
  result it pulls the next due concept in the topic (engine-selected, no `concept_id`), header +
  result label follow the response's `concept_text`. The seed of the session flow (doc §5).
- **Home hero → `GET /next-action`** (`home.tsx`, `fetchNextAction` in `lib/retrieval.ts`). The
  mock "3 concepts slipping…" hero is gone; the engine now picks the single highest-value thing
  (kind cascade review→calibration→dump→new→get_ahead), shown with a kind-lead label + topic +
  the warm `reason` + `est_minutes`. "Start review" opens retrieval straight into the chosen
  mode/topic/concept. Loading, caught-up ("Nothing due right now"), and no-concepts states
  handled. This is the fast path's first surface (doc §3).
- **Answered the user's two side-questions:** "keep going" was dropped only because `/next` lacked
  the concept term (now fixed); the concept-click flow uses **real** concept ids + a live
  LLM-generated challenge (no stock data) — only the *lighting* on the demo topic is still the
  disposable seed.
- **Verify:** `tsc --noEmit` clean; `eslint` clean on `retrieval.tsx` + `lib/retrieval.ts` +
  `home.tsx`. Backend tests via `TEST_DATABASE_URL=…@localhost:5432/notesos_test`. Not run
  on-device.

### 2026-07-29 — Retrieval / study loop wired (the loop that lights the note for real)

§2.7's first item. `retrieval.tsx` was pure mock (hardcoded biology Q&A, fake grading). Now it
drives a real two-request session against `api/retrieval.py`, which is the **only writer of
ConceptState** — so this is what makes the note's mastery heat-map light organically (was 0 real
attempts; the note was lit only by the disposable seed).

- **New `lib/retrieval.ts`** — typed client mirroring `api/retrieval.py`: `fetchModes`,
  `nextChallenge`, `submitAttempt`, `revealSolution`, `recapNext`/`recapAttempt`,
  `dumpNext`/`dumpAttempt`. Types for the sanitized `NextChallenge` payload, `AttemptResult`
  (outcome + FSRS `state` + `calibration`), `RevealResult`, and the free-recall shapes.
- **The session flow (system-spec §5, preserving the LOCKED layout — data only):**
  - **next → confidence → answer → attempt → result.** `POST /next` picks the *handed* concept
    (`concept_id` from the note's id-chain) and has the mode pose a challenge; the answer key
    stays server-side under `challenge_id`. The **confidence beat is captured BETWEEN seeing the
    challenge and answering** (the calibration signal) — kept for posed modes (quiz/pretest) as
    the mock had it; open/free-recall skip it (backend accepts null). `POST /attempt` returns the
    real outcome, the advanced schedule ("next review in N days"), and calibration
    (predicted vs actual → *calibrated / underconfident / overconfident* copy).
  - **Mode → shape map** (drives rendering off the real payload, not mock arrays):
    `quiz`/`pretest` = **posed** (MCQ renders `answer_options`; `short_answer`/`essay`/`numeric`
    → text input); `ramble`/`teach` = **open** (one written response, AI-graded, shows
    `key_points_missed`); `recap`/`dump` = **free-recall** (`/recap|/dump` next+attempt, one
    response graded across many concepts → per-concept grade table).
  - **Worked STEM (B9)** — `question_type:"worked"` gets the reveal flow: predict confidence →
    **`POST /reveal`** (stamps confidence server-side, returns the worked solution) → 4 honest
    self-grade buttons → `/attempt` with the grade. Ordering (confidence-before-reveal) is the
    backend's guarantee; the UI respects it. No STEM notes exist yet, so this is validated by
    construction against the contract.
  - **Modes driven off `GET /modes`** (registry = quiz/pretest/ramble/teach); recap/dump appended
    client-side when a topic is in scope (they're free-recall surfaces outside the registry).
    Falls back to the built-in list if `/modes` fails.
- **Drift / deferred (flagged, not faked):**
  - **Voice answering** — the mock's voice tab/`(preview)` link is gone this pass; it's §2.8
    (`/ws/voice`, premium-gated). Retrieval reads/writes text only.
  - **Paper photo (B8)** — `/transcribe` (handwriting photo → confirm → `answer_origin:"paper"`)
    is a real, distinct sub-flow; deferred to a dedicated retrieval pass. The mock's fake photo
    tab was removed rather than left non-functional.
  - **Mock timed test removed** — `?mode=test` (hardcoded questions, client-side grading) was
    fabricated data. It now shows an honest "coming soon" placeholder; the real thing is
    testbuilder's item (wire to `/api/practice-tests`), not a retrieval mode.
  - **"Keep going" (continuous session)** — dropped: `/next`'s response carries `concept_id` but
    not the concept *term*, so a next-due concept would be mislabeled. The honest loop is
    back-to-note (re-lights on focus) → tap the next term. A backend follow-up (return the term
    in `NextResponse`) would unlock in-screen continuation.
  - **Home hero ("Start review", no params)** stays out of scope — with no topic/concept it shows
    the guidance empty state. Wiring it to `GET /next-action` is a follow-up.
- **Verify:** `tsc --noEmit` clean; `eslint` clean on `retrieval.tsx` + `lib/retrieval.ts`.
  Used `useFocusEffect` (not `useEffect`) for the challenge load so the synchronous state resets
  don't trip `react-hooks/set-state-in-effect` (same pattern as the other screens). Not run
  on-device (owner runs the dev build). **Optional cleanup once real attempts exist:** drop the
  14 seed `concept_states` on topic `71778267-…` (see the 07-29 seed log entry).

---

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
- **Biometric local auth (Face ID / fingerprint).** User weighed it 2026-07-27 and chose
  skip for launch — phone+password + the SecureStore session covers it. If wanted later:
  `expo-local-authentication` gating a stored-session unlock on app open + a settings
  toggle; it does *not* replace phone+password login.
- **Dark mode toggle ("Night Journal").** User decided 2026-07-28: auto/system is fine for
  launch. Deferred as a theming task — a real toggle needs `ThemeProvider` wiring + a
  persisted preference (the `user.preferences` bag or local storage). Not launch-scoped.
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

**Global, not NG-only — two different jobs, two different rules:**

- **The user's OWN number (register/login): explicit country picker, NEVER guessed.**
  Superseded the earlier device-region-guess approach 2026-07-27 after it mangled a
  Nigerian `0813…` into `+44…` on a GB-locale phone (a national number that's *also* valid
  in the device's country parses to the wrong country). `login.tsx` now uses `PhoneInput`
  (`components/ui/PhoneInput.tsx`) — a searchable country/dial-code picker (data in
  `lib/countries.ts`) + national-number field — and `composeE164(country.code, national)`
  in `lib/phone.ts` builds the E.164 from the *chosen* country. Device region only
  *pre-selects* the picker. A user who types a full `+…` number overrides the picker. This
  fully closes the old "register in international format or it's wrong" caveat.
- **CONTACTS (the address book): device region is the right default.** Contacts are stored
  in the phone owner's own local format, so `canonicalPhone` (in `lib/contacts.ts`) keeps
  using `expo-localization` device region — a US user's `(415)…` and a Nigerian user's
  `0803…` both canonicalise from the same book. International `+…` ignores region either way.

The server's `DEFAULT_PHONE_REGION` (`NG`) now only matters as a no-op: the client always
sends E.164, so the server re-canonicalises already-`+…` input region-independently.

**Regenerating `lib/countries.ts`** (245 countries, names baked in because Hermes lacks
`Intl.DisplayNames` at runtime): run in `mobile/` —

```js
node -e "const {getCountries,getCountryCallingCode}=require('libphonenumber-js');const n=new Intl.DisplayNames(['en'],{type:'region'});const flag=c=>String.fromCodePoint(...[...c].map(x=>0x1F1E6+x.charCodeAt(0)-65));const rows=getCountries().map(c=>({code:c,name:n.of(c)||c,dialCode:getCountryCallingCode(c),flag:flag(c)})).filter(r=>r.name!==r.code).sort((a,b)=>a.name.localeCompare(b.name));console.log(JSON.stringify(rows,null,2));"
```

Multi-region hardening later = confirm both libphonenumber ports still agree; the seam is there.

Each ships behind tests and one screen/flow at a time, per the top-of-doc rule.
