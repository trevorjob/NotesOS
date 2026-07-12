# NotesOS v2 — Backend Redesign Plan

> **Living document.** The execution plan for rebuilding the NotesOS backend on the
> emergent-set architecture. This is the *what / how / status*; the *why* lives in
> [`NotesOS_Architecture_NextPhase.md`](../NotesOS_Architecture_NextPhase.md)
> (canonical on conflict) and [`NotesOS—Product_Brief.md`](../NotesOS—Product_Brief.md).
>
> Last updated: 2026-07-11.
>
> **Launch definition:** the product design is finalized (see the locked notes in
> [`product-map.md`](./product-map.md)). The **Launch build queue** below turns every
> locked decision into a checkable workstream. **When the queue is all green, we are done —
> we stop and ship.** "Green" = built + tested (real-Postgres per the conventions) +
> documented. The system-behaviour contract the native client designs against lives in
> [`system-spec.md`](./system-spec.md).

## Anchor

We are turning NotesOS into a real product. The spine is:

```
School → Course → Topic → Resources
```

The cohort/"set" is **emergent** — computed from shared course enrollment, never a
stored container. Your classmates are the people in your courses. Where education
is cohort-based the graph clusters tight; where it's credit-based it stays loose.
One design, no per-country branching.

## Working conventions (how we build)

| Rule | Detail |
|---|---|
| **Backend-only** | This effort touches the FastAPI backend only. The Next.js web frontend is **not** touched — the v2 client will be a native app (designs pending). |
| **v1 is separate** | The live web app (v1) lives on its own branch/env. This env is v2; changes here don't affect live users. Hard deletes are safe. |
| **No hand-written migrations** | Models are the source of truth. Schema migrations come from `alembic revision --autogenerate`. Extensions live in `init_db()`; seed/reference data lives in `scripts/`. |
| **Infra is the owner's job** | Claude does not run docker/db/migrations/installs. It writes code + tests and documents the infra steps to run. |
| **Tests guard the surgery** | pytest against a real Postgres (`notesos_test`), schema built from models, TRUNCATE between tests. New logic ships with tests. |

## Key architecture decisions

1. **Emergent set, not a cohort entity.** No School→Cohort→Semester container tree.
   Classmates derive from `course_enrollments` overlap.
2. **School is the top of the spine and the proximity-check hard filter.** Canonical
   `normalized_name` dedupes "Unilag"/"UNILAG"/"University of Lagos". Students pick
   from a curated list or type one in (canonicalised on the way in).
3. **Terms are user-created and structured.** A reusable, user-scoped `Term` (personal
   filing, no members/owner) composed from controlled components —
   `division_type` + `division_value` + optional `study_level` — into one canonical
   label ("200 Level · Second Semester", "Year 1 · Term 2", "Fall Semester").
   Deterministic composition → identical choices yield identical strings (uniformity)
   while each system uses only the pieces it needs (portability). Courses are *filed*
   under a term via `course_enrollments.term_id`.
4. **No public/private courses.** Every course has an invite code. Reached by
   creation, classmate-graph discovery, or a direct invite.
5. **The proximity check is the core primitive** (Phase 2). Before something is
   created, check whether it already exists nearby and offer it. School is the hard
   filter; ranking is program > entry year > shared courses. It never forces a merge —
   every check ends in an offer, and "make my own" stays live.
6. **Governance without moderators** (Phase 4). The Merge Agent gates uploads on
   embedding coherence (quarantine wildly off-topic ones); corroboration down-weights
   lone contradictions. Three ownerless regulators: proximity check (structure),
   Merge Agent gate (quality), contribution visibility (behaviour).

## Roadmap & status

### ✅ Phase 0 — Foundations
- pytest harness (Postgres, model-built schema, per-test TRUNCATE, HTTP + DB fixtures).
- Enrollment integrity: real `UniqueConstraint(user_id, course_id)` — the classmate
  graph is computed from this table, so it must be trustworthy.
- Queue hardening: one shared `run_worker_loop` for all 7 workers; retry + backoff +
  dead-letter; fixed the crashed-job "ack-and-lose" bug; brought the 2 legacy
  workers onto the reliable path.

### ✅ Phase 1 — Entity migration
- **School** entity + canonicalisation service (exact → alias → trgm fuzzy), curated
  Nigerian seed, public `/api/schools/search` typeahead, `users.school_id` +
  `courses.school_id`.
- **User signals** (all optional): `program`, `entry_year`, `phone` (unique-when-present);
  wired into register + profile; school resolved at signup.
- **Terms**: `Term` entity + composer/vocab service + `/api/terms` (vocab/list/create/
  update/delete) + course filing (`term_id`, plus `PATCH /courses/{id}/term`).
- **Removed** the container entities: `Semester`/`SemesterMember`, `Class`/`Classmate`,
  `/api/semesters`, `/api/invites`, and `courses.semester_id` / `courses.semester`.
- **Removed** public/private (`courses.is_public`).

### ✅ Phase 2 — Proximity check (course mode)

Fuzzy "did you mean this?" on course creation. Implemented in
[`services/proximity.py`](../backend/app/services/proximity.py), wired into
`POST /api/courses`.
- **School = hard filter** (no school on creator ⇒ no check ⇒ straight create).
- **Text match** finds candidates (trgm on code/name; exact code always qualifies;
  `PROXIMITY_MATCH_THRESHOLD = 0.3`, the single tuning knob — start loose).
- **People signals rank them**: program > entry_year > shared classmates
  (classmate = shares ≥1 course with the creator, from the emergent graph);
  text similarity only breaks ties.
- **Offer, never force**: a near-match returns HTTP 200 `{proximity_check, matches[]}`
  and creates nothing; the client re-POSTs with `force=true` to fork. Each match
  carries `member_count` + `signals` so the client can say *why* it's offered.
- Merge path is the existing `POST /api/courses/join`.
- **Known gap:** `POST /api/courses/batch` still bypasses the check (bulk import —
  an offer-per-item flow doesn't fit its all-or-nothing contract). Revisit if
  batch becomes a fork vector.

### ✅ Phase 3 — Emergent graph + discovery

Classmate queries over enrollment overlap, exposed via a discovery API. Service
in [`services/discovery.py`](../backend/app/services/discovery.py), router
[`api/discovery.py`](../backend/app/api/discovery.py) at `/api/discovery`.
- **`GET /api/discovery/classmates`** — the emergent set: everyone you share ≥1
  course with, ranked by shared-course count.
- **`GET /api/discovery/courses`** — "courses your classmates are taking" that
  you're not in, ranked by classmates-here > resource_count > member_count.
- **Activity gate**: a course surfaces only once it clears `ACTIVITY_MIN_RESOURCES`
  (an upload) *or* `ACTIVITY_MIN_MEMBERS` (a second member) — a solo empty course
  is invisible weight and stays invisible. These two constants are the tuning knob.
- **Notify-don't-enroll**: both endpoints are pure reads; discovery surfaces, the
  existing `POST /api/courses/join` is the only join primitive. Verified by test.
- **Removed** the public `join?search=` browse branch + `JoinCourseRequest.search`
  — the graph is the discovery surface, so public browse is gone.
- No schema change — discovery is query-only over existing tables.

### ✅ Phase 4 — Merge Agent gate
Governance without a moderator — the gate is a worker, not a person.
[`services/merge_gate.py`](../backend/app/services/merge_gate.py) computes per-resource
embedding coherence (max cosine of a resource's chunk centroid to any *other* resource
in the topic) and quarantines the ones that corroborate with nothing.

- `Resource.quarantined` / `quarantine_reason` / `quarantined_at` columns.
- Runs in `knowledge_worker` **before** synthesis; the synthesizer and quiz generator
  both exclude quarantined resources, so off-topic uploads never reach the shared note
  or generated tests.
- **Release valve**: a quarantined upload is let back in automatically once later
  material makes it corroborate — the same gate clears the flag.
- **Cold start respected**: below `MIN_CORPUS` (3) resources there's no topic shape to
  be an outlier from, so everything passes. `COHERENCE_THRESHOLD` (0.30) is the knob.
- **Uploader-only visibility**: the resource list hides quarantined items from everyone
  but their uploader (who sees them flagged); the list cache is now user-scoped.
- Corroboration *weighting* (down-weighting contradicted claims) still deferred.
- Schema change: 3 additive columns on `resources` → autogenerate a migration.

### ⏳ Phase 5 — Native app (parallel track)
New client (Expo/React Native) against this API once Phase 1 stabilises. Contact
discovery (phone-hash matching) seeds cold start. Awaiting designs.

### ⏳ Phase 6 — Coordination mode + pricing infra
Proximity-check mode 2 ("someone's already building this test, want in?"); group-
dynamic pricing scaffolding (present, not pushed). **Note:** sharded/scale pricing was
**retired** (product-map Access model) — it only held when NotesOS was a pure shared-read
product; retrieval is per-seat and doesn't amortize. Launch is **free** (observe cost +
behaviour first), so pricing infra is post-launch.

### ✅ Retrieval engine track (ran parallel to Phases 0–6)
The product's center of gravity. **Pass 1 & 2 done, tested (114 green).**
- **Substrate:** `Concept` / `ConceptState` (FSRS) / `RetrievalAttempt` (append-only).
- **Scheduler:** FSRS (`services/retrieval/scheduler.py`), the only fsrs-touching file.
- **Modes (plugins over one Protocol):** quiz · ramble · teach · pretest.
- **HTTP surface:** `POST /api/retrieval/next` → `/attempt`, `GET /modes`; per-attempt
  **calibration** (predicted vs actual) in the response.
- **Dormant recognition seam** (`services/retrieval/recognition.py`, topic-level
  attribution, gated behind `ENABLE_RECOGNITION=false` — resolves beneficiaries, delivers
  nothing until §11 + the notification digest land).

## Launch build queue (the product build — "all green ⇒ ship")

> Turns the locked product design ([`product-map.md`](./product-map.md)) into an ordered,
> checkable queue. **Three phases by dependency.** Launch = **Phase A + the needed Phase B**
> green, then the **native client (Phase C)** built on top. Each item's *Green when* is its
> acceptance bar. Behaviour details for every item are in [`system-spec.md`](./system-spec.md).

### Phase A — backend, no native dependency (start here)

- [x] **A0 · Auth: phone-primary migration.** ✅ *(2026-07-12)* `phone` is now required + unique +
  OTP-verified; `email` is nullable/optional (unique-when-present). Flow: `register` creates an
  unverified user + sends an OTP (no tokens) → `verify-otp` issues tokens → `login` is phone+password
  and requires a verified phone; `otp/resend` re-issues. Google OAuth: an existing verified user logs
  straight in; a **new** identity gets a short-lived `oauth_token` and must complete `oauth/register`
  (enters a phone) → `verify-otp` — the phone is **never inferred from Google**. OTP delivery is a
  swappable provider (`OTP_PROVIDER`, default `console`) behind `services/otp.py` — the single seam;
  the code is stored hashed on the user (mirrors password-reset, no new table). Migration
  `2d355456bd16` autogenerated (owner runs `upgrade head`). 123 tests green. *(Foundational — powers
  reliable contact discovery.)*
- [x] **A1 · Streaming + model tiering.** ✅ *(2026-07-12)* `call_llm_stream()` (async generator,
  OpenAI-compatible SSE) sits beside `call_llm`, sharing routing/message-building. Tiering is
  first-class: each task resolves to a **(provider, model)** via a task map + a `fast|standard|heavy`
  tier spec, **overridable per task** with `LLM_<TASK>` (a provider name for back-compat *or* a tier
  name). Synthesis moved to the heavy tier (`gpt-4o`); interactive/deterministic tasks stay fast.
  Streaming is exposed as SSE on the tutor surface — `POST /api/study/ask/stream?course_id=…` emits
  `meta`/`token`/`done` frames and persists the full answer identically to the blocking route
  (`study_agent.ask_question_stream`, prompt-building shared via `_build_answer_messages`). No UI
  consumes it yet — validated by tests (tier resolution, SSE parse, faked-transport stream, and the
  end-to-end SSE endpoint incl. enrollment gate). 136 tests green. *(Speed + cost double-pay.)*
  **Streaming coverage (decided 2026-07-12):** the tutor is the only surface that token-streams
  cleanly today; every other LLM surface is **structured-JSON** (synthesis, question-gen, research,
  grading — parsed whole) or **record-bound** (retrieval `/next` + `/attempt`: the grade must be
  parsed before the append-only attempt + FSRS + recognition fire). Those are **intentionally not
  streamed in A1.** Plan for the rest: **synthesis → progressive note over the WebSocket, built in
  A4** (which already rewrites that pipeline — streaming it now is throwaway); **quiz/feedback →
  streaming the challenge/feedback prose changes the mode `evaluate`/record flow, so it's an
  architect call (build-guide §7), not a solo reshape.** See build-guide §4 (A4) + §5.
- [x] **A2 · Capture overhaul.** ✅ *(2026-07-12)* **Audio ingestion:** `ResourceKind.AUDIO` +
  audio exts on the shared allow-list (`services/capture_types.py` — one list, every entry point);
  audio uploads → Whisper (`{"type": "audio"}` transcription job, real container ext passed) →
  chunking → the normal pipeline. Markdown/plain-text (`.md`/`.txt`) also accepted (decode-only).
  **Outline scaffold:** `POST /api/courses/{id}/outline` (paste and/or snapped photos → vision →
  LLM parse, fast tier) creates ordered empty topics, dedupes case-insensitively (communal artifact
  — a classmate re-adding duplicates nothing), and persists the raw syllabus to `course_outlines`.
  **Dump→auto-organize:** `POST /api/courses/{id}/capture` returns **202 instantly**; the new
  `capture` worker transcribes the pile (concurrent, per-file error isolation), then **classifies**
  into known topics when an outline/topics exist or **clusters (greedy cosine) + LLM-names** when
  not, **auto-files** (LOCKED opt-out model — material lands even if nobody confirms; unmatched
  files fall to "Unsorted", never dropped), hands every resource to chunking → merge gate →
  synthesis, and broadcasts `capture_progress`/`capture_complete`/`capture_failed` WebSocket
  events. **Honesty seam:** `ocr_confidence` derived from the transcript's own `[?]`/`[illegible]`
  markers; `needs_review` (derived, not stored) in every resource payload. **Tweak primitive:**
  `PATCH /resources/{id}/move` (uploader-only, same-course; re-synthesizes both topics). Images
  keep their figure attached as a `ResourceFile`. Migration `d8badee7f31a` (enum values, via
  `alembic-postgresql-enum` so autogenerate sees enum members). 153 tests green. *(The front door.)*
- [ ] **A3 · Session + Recap.** Derive the session from the append-only attempt log (≥15-min
  idle gap closes it — no session table). Recap mode (free recall of last session; topic-scoped
  first). *Green when:* session boundaries derived + queryable; recap generates/grades an
  attempt-per-concept; tests. *(Keystone — also unblocks multi-turn later.)*
- [ ] **A4 · Incremental synthesis.** Append-merge new material into the existing note instead
  of full rebuild; debounce bursty uploads. *Green when:* re-synthesis is incremental (not
  whole-corpus); "what changed" derivable; cost drop measured; tests. *(Kills the
  write-amplification cost bomb.)*

### Phase B — backend, has prerequisites

- [ ] **B1 · Attribution/consumption layer (§11) → recognition live.** The consume-event
  substrate (who-made-the-thing tagged on each consume). Then flip `ENABLE_RECOGNITION`.
  Warmth rules first (aggregate passive, warm active).
- [ ] **B2 · Notification / habit delivery.** Decay digest (next-best-action selector, shared
  with the home card); batching; warm+mild voice; timing off the session log; preferences.
- [ ] **B3 · Next-best-action selector.** "Highest-value retrieval right now" from FSRS due +
  calibration gaps + what's new. Powers the home card (pull) and the digest (push) — one engine.
- [ ] **B4 · Subject profiles (STEM first).** Profile = {rendering + mode-mix + grading}.
  **Replace the loose pass-2 `subject_type` strings** with a closed enum
  **`SubjectFamily = STEM · LANGUAGE · HUMANITIES · GENERAL`**; **infer it at synthesis** and store
  `subject_family` on the Topic (user-overridable; concepts inherit); centralize the family→mode
  affinity in one **profile map** (modes stop string-matching subjects). Then the STEM profile:
  worked-example + self-graded-calibration modes. Language is a later profile — the abstraction
  holds it. *Green when:* enum + topic field + synthesis inference + profile map replace the ad-hoc
  strings; STEM profile drives a real mode mix; tests.
- [ ] **B5 · Real-time voice lane (premium).** Streaming STT + LLM + TTS, overlapped; VAD
  endpointing; barge-in; the grade emitted off-turn by the same streaming call. Separate from
  the batch voice workers.
- [ ] **B6 · Offline sync endpoints.** Bulk course pull; delta invalidation (`last_synced_at` →
  changed IDs); append-only event push. Event-sourced (derive `ConceptState` from the log).

### Phase C — needs the native client (Phase 5 designs)

- [ ] **C1 · Home / one-card entry** (doorway-not-dashboard; review-default hero).
- [ ] **C2 · Active-surface note canvas** (note↔concept linking, rendered math, "says who?" X-ray).
- [ ] **C3 · Spatial progress** (notes lit by mastery; calibration surfaced when needed).
- [ ] **C4 · Capture dump UX** (drag/snap/record → confirm the proposed topic structure).
- [ ] **C5 · Offline local store + background sync** (cache-first; boundary + 10–15 min poll).
- [ ] **C6 · Voice conversational UI** (co-presence, active-listen seams).
- [ ] **C7 · Onboarding flow** (gap-first pretest opening; hybrid demo-while-processing).
- [ ] **C8 · Contribution visibility** (§6 — "N built this note," no leaderboard).

### Explicitly deferred past launch (🔮)
Video embed · live study rooms / competitive quizzing · coordination-mode polish · language
subject profile · timing/sleep-aware delivery · speech-emotion calibration · gift-a-connection
+ pricing infra (launch is free) · automated STEM method-grading (self-graded ships first).

## Current v2 schema (new/changed)

- `schools` (id, name, normalized_name unique, country, aliases jsonb)
- `terms` (id, user_id, division_type enum, division_value, study_level, label; unique per user+label)
- `users` += school_id, program, entry_year, phone
- **Auth identity change (2026-07-11):** **phone is the primary identity** — `phone` becomes
  required + unique (OTP-verified, likely WhatsApp), `email` becomes nullable/optional. Google
  OAuth stays but still collects a phone. Fits the communal/contact-discovery substrate + the
  phone-first market; push replaces email's notification job. Small migration; phone was already
  unique-when-present. (An auth workstream, not yet in the build queue — slot into Phase A.)
- `courses` += school_id; − semester, − semester_id, − is_public
- `course_enrollments` += term_id; unique(user_id, course_id)
- **Dropped tables:** semesters, semester_members, classes, classmates
- **Note:** the classmate graph is *emergent* — computed from `course_enrollments`
  overlap (Phase 3 discovery), never a stored table.

## Infra runbook (owner)

Fresh DB:
```bash
psql "$DATABASE_URL" -c "CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pg_trgm;"
cd backend && alembic revision --autogenerate -m "v2 baseline" && alembic upgrade head
python -m scripts.seed_schools
```
Tests: recreate `notesos_test` empty, then `pytest`.

## Open questions (from the architecture doc)

- **Matcher reach.** Too loose → prompt fatigue; too tight → accidental forks slip
  through. Start loose and tighten, or strict and loosen? Resolve by watching Phase 2 run.
- **Onboarding asks.** Program/major is a clean signal in most of the world but a US
  first-year often can't answer it. Optional field + contact discovery, or "undeclared"
  as a real bucket?
- **Coherent-but-wrong uploads.** The Merge Agent gate catches incoherence, not subtle
  wrongness. Care now, or wait for crowd-correction density (Phase 4)?
