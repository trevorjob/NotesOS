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
- [x] **A3 · Session + Recap.** ✅ *(2026-07-12)* **Sessions are derived, never stored**
  (`services/retrieval/session.py`): a session is a *query* over `RetrievalAttempt` ordered by
  time, cut on a ≥15-min idle gap (`SESSION_IDLE_GAP`). Pure `split_sessions()` + scoped
  `get_sessions()`/`last_session()` (newest-first, capped scan). Queryable via
  `GET /api/retrieval/sessions` (optional course/topic scope). **Recap** (`services/retrieval/recap.py`)
  is the many-concepts/one-turn **stretch** of the mode Protocol — deliberately *not* a registered
  `RetrievalMode`: `build_recap()` opens an **uncued** free-recall prompt over the last session's
  concept set (topic-scoped; never leaks the concept text); `grade_recap()` judges the single
  monologue in **one** `recap_eval` LLM call (heavy tier) and records an **append-only attempt per
  concept** through the engine — FSRS, calibration seam, and recognition all fire per concept. A
  concept the monologue never surfaces scores 0 → a lapse (the forgetting the recap exists to
  expose); a blank response never reaches the model. HTTP: `POST /api/retrieval/recap/next` +
  `/recap/attempt` (own Redis handoff, single-use, enrollment-enforced, 404 with no prior session).
  **No migration** — derived + reuses `RetrievalAttempt` (`mode="recap"`). 174 tests green (+20).
  *(Keystone — also unblocks multi-turn later.)*
- [x] **A4 · Incremental synthesis.** ✅ *(2026-07-12)* **Append-merge, not full rebuild.**
  Per-resource `Resource.synthesized_at` marks what's already in the note; NULL = unmerged, so a
  fresh upload, a **quarantine release**, and a **moved-in** resource are all expressed the same
  way (nothing special-cased). The synthesizer (`knowledge_synthesizer.py`) picks a mode per run:
  **full** (no usable note yet, or `force_full`), **incremental** (existing note + only the pending
  resources — reconcile/dedupe prompt), or **noop** (nothing pending → **skip the LLM entirely**,
  the cost win). Only chunked, non-quarantined resources are ever merged/stamped; quarantined
  uploads are never read. **"What changed" is derivable** (order resources by `synthesized_at`).
  **Debounce** (`services/synthesis_debounce.py`): `schedule_synthesis()` gates the enqueue to one
  knowledge job per topic per window (`SYNTH_DEBOUNCE_WINDOW_SEC`), so a chunking burst coalesces;
  `force_full`/`bypass_debounce` are the escape hatches. Stragglers that finish chunking after a
  pass reads its snapshot are caught by a **trailing re-schedule** — the worker checks the DB (not
  the window) for still-pending material and re-runs (strictly decreasing → terminates). **Streaming
  lands here (deferred from A1):** the note **body streams** as markdown prose via `call_llm_stream`,
  broadcast over the course WebSocket (`knowledge_stream_start`/`knowledge_delta`/`knowledge_stream_end`
  published to `course_updates` — worker→client via Redis pub/sub, best-effort); the structured
  metadata (`key_points`/`concepts`) is extracted from the finished body in a second cheap
  whole-parsed `knowledge_metadata` (fast-tier) call. Prose streams, JSON arrives whole — never a
  half-parsed blob. Triggers rewired: chunking worker + capture (debounced), manual regenerate
  (`force_full`), move (source rebuild + dest incremental). **Migration needed** — `Resource.synthesized_at`
  (owner: `alembic revision --autogenerate` + `upgrade head`). 188 tests green (+14). *(Kills the
  write-amplification cost bomb — every re-synthesis is O(new), not O(corpus). **Phase A complete.**)*

### Phase B — backend, has prerequisites

- [x] **B1 · Attribution/consumption layer (§11) → recognition live.** ✅ *(2026-07-13)* The
  §11 consume substrate is **one new table for the one thing not already stored**: passive
  consumes. `ConsumeEvent` (`models/consume.py`, topic-level per invariant #8) records
  **`NOTE_VIEW`/`AUDIO_LISTEN`** — while **active** consume derives from the append-only
  `RetrievalAttempt` log (never duplicated). `services/retrieval/recognition.py` grew from a
  dormant seam into the recognition policy: `record_consume()` (best-effort, isolated commit,
  records regardless of flag — it's substrate), `pending_recognition()` (aggregates active +
  passive over `[since, now]`, distinct users, **excludes the contributor's own activity**),
  and `deliver_pending_recognition()` — **one batched, warmth-tuned notification** (warm for
  active, aggregate/anonymous for passive; the studier is never named), flag-gated, and the
  function **B2's tick will call**. `on_attempt()` stays at the `/attempt` + recap call sites
  but **no longer delivers per-attempt** (that spammy placeholder is gone). Note/audio GETs
  record the passive consume. `ENABLE_RECOGNITION` flipped **False → True**. Migration
  `a1fca0528a36` (owner: `upgrade head`). 194 tests green (+6). *(Delivery cadence is B2 —
  recognition folds into the notifications tick.)*
- [x] **B2 · Notification / habit delivery.** ✅ *(2026-07-13)* The **periodic** worker — the
  deliberate exception to the reactive queue loop (build-guide §2a): all logic in
  `services/digest.py` (apscheduler-free, unit-tested), driven by an **APScheduler** hourly
  tick in `workers/notification_scheduler.py` (added to `run_workers.py` as `notifications`;
  `apscheduler` added to `requirements.txt` — **owner installs**). Two batched, rare loops:
  the **decay nudge** (primary/weight-bearing) pulls B3's selector and pushes **only** fading
  knowledge (`review`/`calibration` — never nags about new material / get-ahead), and
  **recognition** (secondary) fires B1's `deliver_pending_recognition`. **Timing off the
  session log** — `user_preferred_hour` infers each user's study hour from attempt timestamps
  (no stored schedule); **batching** — `last_digest_at` caps it to one attempt/user/day;
  **preferences** — `NotificationPreference` (both loops opt-out, on by default) +
  `GET/PATCH /api/notifications/preferences`. New `NotificationType.DECAY_NUDGE`. Migration
  `911eae9c1853` (table + enum value; owner: `upgrade head`). 217 tests green (+12). *(B1 + B3
  now have a heartbeat.)*
- [x] **B3 · Next-best-action selector.** ✅ *(2026-07-13)* One engine
  (`services/retrieval/next_action.py`) behind "what should I study now?", pulled by both the
  home doorway and the B2 digest. Pure query — no schema. **Strict cascade** (fading wins):
  **review** (FSRS `due <= now`) → **calibration** (predicted ≥ 0.6 but graded `again`/`hard`
  in the last 30d — the fluency illusion made visible) → **new** (concepts in an enrolled
  course never attempted → opens with a **pretest**) → **get_ahead** (scheduled but nothing
  due). Everything **topic-scoped** (the study unit); returns the topic with the most fading
  concepts, a warm specific `reason`, a suggested `mode`, and a bounded `est_minutes`.
  **Never empty-handed** — returns `None` only when the user has *no* concepts at all (client
  routes to capture). Pull surface: `GET /api/retrieval/next-action?course_id=&topic_id=`
  (enrollment-gated, `null` when nothing to do). 205 tests green (+11). *(Powers B2's push +
  the C1 home card.)*
- [x] **B4 · Subject profiles (STEM first).** *(done 2026-07-13)* Profile = {rendering + mode-mix +
  grading}. Closed enum **`SubjectFamily = STEM · LANGUAGE · HUMANITIES · GENERAL`**
  (`models/subject.py`); stored on the Topic (`subject_family` + `subject_family_overridden` lock;
  concepts inherit — no concept column). **Inferred at synthesis** — the metadata pass now emits a
  `subject_family`, folded onto the topic unless the user has overridden it (`_apply_subject_family`).
  The loose per-mode `subject_weight(subject_type)` strings are **deleted** — the family→mode affinity
  now lives in ONE profile map (`services/retrieval/subject_profiles.py`, keyed by mode + family); the
  mode Protocol no longer mentions subjects. STEM profile = worked-example (pretest) + self-graded
  calibration (quiz), `render=math`, `grading=self_calibration`. The mix is **real**: `next_action`
  picks the mode from the topic's family (STEM→quiz, LANGUAGE→ramble, HUMANITIES→teach; `new` stays
  pretest — a pedagogical invariant). Surfaces: `GET /api/retrieval/modes?family=`,
  `GET|PATCH /api/retrieval/topics/{id}/profile` (enrollment-gated; PATCH locks the override). Recap
  gets a profile affinity in every family (it's a log-level mode, not a registry mode). Migration
  `9aad224787f6`. 239 tests green (+22). *(Language/humanities profiles ship later — the map holds them.)*
- [x] **B5 · Real-time voice lane (premium).** *(done 2026-07-13)* A NEW streaming conversational
  surface (`services/voice/` + WS `api/voice.py`), separate from the batch workers **and** from the
  LOCKED retrieval `/attempt` contract (§134) — it's an orchestration like recap, not a mode. One
  `VoiceLane` per live session over one concept: the user's turn (client-side STT, text-only in)
  drives (a) a **streamed spoken reply** — LLM prose token-by-token (`voice_chat` task, fast tier)
  with **TTS synthesized per sentence** so audio starts before the reply ends (the STT/LLM/TTS
  overlap; `SentenceBuffer` is the seam) — and (b) an **off-turn grade** that reuses the underlying
  mode's `evaluate` (ramble/teach only; objective modes rejected) and records **append-only via
  `engine.record_attempt`** under the real mode key with `challenge={"lane":"voice"}` — *no new
  grade path, no `/attempt` touch, no Protocol change, no migration.* The grade is about what the
  *user* said, so it **survives barge-in**: a `barge_in` frame trips the turn's cancel event,
  stopping speech (→ `interrupted`) but never the recorded attempt. Lifecycle states match
  system-spec §14.5 (listening → thinking → speaking → interrupted → done). Premium-gated behind
  `ENABLE_VOICE_LANE` (default off — launch is free; per-user entitlement slots into
  `authorize_voice`, the one testable security seam: flag → JWT → enrollment). All three boundaries
  (reply/TTS/grade) injectable → fully tested without a live model or audio. 267 tests green (+10).
- [x] **B6 · Offline sync endpoints.** *(done 2026-07-13)* Three endpoints over the append-only log
  (`services/sync.py` + `api/sync.py`, self-prefixed `/api/sync`): **bulk pull**
  `GET /courses/{id}` (topics + concepts + notes + *this user's* derived `ConceptState` + a
  `server_time` the client stores as `last_synced_at`); **delta invalidation** `GET /changes?since=`
  (IDs of topics edited / notes re-synthesized / concepts added since — client marks stale, refetches
  on nav); **append-only push** `POST /attempts` — replays locally-queued attempts, **idempotent** via a
  client-generated `client_event_id` (new unique col on `RetrievalAttempt`; a retried push never
  double-applies), replayed in **device-timestamp order** so FSRS advances exactly as online, keeping
  each attempt's original `created_at`. **Event-sourced:** the server *derives* `ConceptState` by
  replaying — it stores no client-computed schedule. Only objective/self-graded modes (`quiz`/`pretest`)
  may push; AI-graded (ramble/teach) stay online-only. Partial-failure safe (one bad event is rejected,
  not the batch); enrollment-gated per event. Migration `c992b8fa8e83`. 257 tests green (+18).

- [x] **B7 · Brain dump.** *(added + done 2026-07-17)* Recap's machine, topic-set selector — built
  exactly as locked. `recap.grade_recap` gained a `mode_key` param (default `"recap"`, recap
  byte-identical; the recorded challenge payload keys off the mode). `services/retrieval/dump.py` =
  the selector: `build_dump()` opens an uncued prompt over the topic's **full** concept set (never
  listing the concepts; reuses `RecapChallenge` — one machine, two surfaces), raises on an empty
  topic. HTTP mirrors recap via a **shared free-recall flow** in `api/retrieval.py`
  (`_open_free_recall`/`_grade_free_recall`, per-kind Redis namespace so a recap challenge can't be
  played as a dump): `POST /api/retrieval/dump/next` (409 empty topic) → `/dump/attempt` — one
  monologue → append-only attempt per concept under **`brain_dump`**, unsurfaced concepts graded
  `again` (the lapse the dump exists to expose). **Next-action gains the read→dump case:** new kind
  `dump` (mode `brain_dump`) offered when a topic in the `new` bucket was **freshly read** — a
  `NOTE_VIEW` consume (B1 substrate) within `FRESH_READ_WINDOW` (24h) and newer than the user's last
  attempt in the topic; derived, never stored. Sits between calibration and new: review/calibration
  still win (strict cascade); stale or acted-on reads fall back to pretest; the digest can't push it
  (`PUSHWORTHY_KINDS` allowlist). `brain_dump` affinities added to every subject profile (mirrors
  recap — same machine). **No migration** — no model change. 280 tests green (+13).

- [x] **B8 · Photo answers — handwriting in, every mode at once.** *(added + done 2026-07-17)*
  One seam, as locked: `services/paper.py` (the paper substrate — voice's written twin) +
  `POST /api/retrieval/transcribe` (multipart, auth-gated). Photo(s) in page order → **ephemeral
  data URLs** into the **existing vision seam** (`vision_transcribe`, `VISION_MODEL` — no new OCR
  path; the prompt already emits LaTeX for equations and flags `[?]`/`[illegible]`) → the response
  carries the transcription **plus `requires_confirmation: true` (a `Literal[True]` — the confirm
  beat is in the contract)** and `has_uncertain`/`has_illegible` flags pointing the user at exactly
  what to correct. Photos are **never stored** — only confirmed text enters the log. Then the
  **unchanged** text flow: `AttemptRequest`/`RecapAttemptRequest` gained an optional
  `answer_origin: Literal["paper"]` **marker** (closed vocabulary, never an image field; `/attempt`
  stays LOCKED text-only/synchronous) folded into the recorded `challenge` payload — so every mode
  (quiz/ramble/teach/pretest/recap/brain dump) gets photo answers at once, modes untouched. Limits:
  jpeg/png/webp only (vision-API data-URL constraint; client converts HEIC), 10MB/page → 413,
  ≤5 pages, wrong type → 415. **Fairness pinned end-to-end by test:** transcribe → user *corrects*
  → the graded attempt records the confirmed text with `challenge.origin="paper"`, on both the
  single-concept flow and a handwritten brain dump. **No migration** — no model change. 290 tests
  green (+10).

- [x] **B9 · STEM worked problems — `self_calibration` made real.** *(added + done 2026-07-17)*
  Built the LOCKED launch dodge on B4's socket — no new mode, no `if family == STEM` branch.
  (1) **Subject-aware generation:** `/next` now hands the topic profile's **grading directive**
  into `ModeContext.extra["grading"]` (alongside the existing family); `QuizMode.generate`
  branches on `grading == GRADE_SELF_CALIBRATION` (never the enum) → `_generate_worked` via a
  new `worked_problem_gen` LLM task (gpt-4o — the solution must be *correct*). One generation
  yields `worked` (self-graded), `numeric` (server-graded), or `conceptual` (falls back to the
  untouched AI-graded short-answer path). LaTeX `$…$` / `$$…$$` — same convention as B8's vision
  prompt and B4 `render=math`. (2) **Reveal beat:** `POST /api/retrieval/reveal` stamps
  `predicted_confidence` into the cached challenge **then** returns the worked solution —
  one-shot (2nd → 409); `worked_solution`/`expected_value`/`tolerance` added to
  `_SENSITIVE_PAYLOAD_KEYS` so `/next` withholds them exactly like `correct_answer`. (3)
  **Deterministic self-grade** (`services/retrieval/worked.py`, LLM-free): `grade_self_report`
  maps a closed vocabulary (again/hard/good/easy) 1:1 onto FSRS grades — rejects anything else
  (400); `/attempt` blocks self-grading before reveal (409) and reads the **reveal-time**
  confidence, ignoring any resent body value (ordering is the calibration guarantee). Note the
  deliberate asymmetry: MCQ caps at `good` (guessing), self-grade may award `easy` (honest
  comparison to a full solution). (4) **`numeric`:** `grade_numeric` = float-parse + tolerance,
  server-side, caps at `good`; solution rides back as feedback (worked-example effect *after*
  committing); no reveal needed (objective). SymPy/symbolic equivalence stays the post-launch
  escalation — not touched. (5) **Procedures-as-concepts:** prompt-level nudge only — synthesis
  metadata prompt now invites STEM "concepts" to be procedures ("differentiate a composite
  function") with a method sketch as definition; no substrate change. Paper (B8) attaches
  optionally — `answer_origin="paper"` flows onto a self-graded attempt; never gated before
  self-grade. Zero-LLM self-calibration attempts stay B6-offline-pushable (mode quiz/pretest).
  **No migration** — no model change. 318 tests green (+28: substrate grading, mode
  directive/regression, reveal ordering & one-shot, self-grade/numeric/paper end-to-end,
  GENERAL byte-identical).

- [x] **B10 · STEM front-of-pipeline — the note + the tutor go subject-native.** *(added + done 2026-07-17)*
  Built family-as-prior, not gate — one content-driven path, no template swap. **(1) The
  synthesis prompt learned math.** A shared `_FORM_RULES` block ("form follows content":
  render math as LaTeX `$…$`/`$$…$$`, keep worked examples/derivations step-intact, code in
  fenced blocks, tables as Markdown — and *don't* inflate a definition into fake steps) now
  rides on **every** note prompt (full + incremental) regardless of family — that missing
  vocabulary was the real bug. The family adds only a one-line `SUBJECT LEAN` on top (empty
  for GENERAL). So a GENERAL econ note renders its one derivation, a prose topic stays prose
  — proven by test (form rules present, no lean, on a GENERAL note). **(2) Classify early.**
  New `_classify_family` runs a cheap fast-tier (`subject_classify`) call on a chunk *sample*
  **before** `_generate_body`, so the lean + client render hint are available; the old
  post-note inference (`_apply_subject_family` + the metadata prompt's `subject_family`
  field) is removed. **User override wins and skips the LLM**; an already-classified family
  is **kept on incremental merges** (no flip-flop off a partial chunk); placed after the noop
  guard so an up-to-date note still does zero LLM work. Robust token parse tolerates a chatty
  reply. **(3) Incremental merge protects worked examples** — an explicit preserve rule +
  base-note fed in (tested). **(4) Subject-aware tutor.** `study_agent` gained
  `_subject_directive` (branches on `profile.render == RENDER_MATH`, **never the enum** — a
  later math family inherits it): on a STEM topic the tutor renders LaTeX and *works the
  example* step by step; injected as a `SUBJECT SHAPE` block **orthogonal to the persona
  axis** (tone/emoji/style untouched). Course-wide chat (no topic) and prose topics stay
  neutral — no regression (tested). SymPy/method-grading stays the locked post-launch
  escalation — untouched. **No migration** — no model change. 330 tests green (+12: form
  rules on every note, GENERAL-not-gated, prose lean, override lock, no-flip-flop, worked-
  example preservation, chatty-parse, tutor shape/persona-orthogonality/neutral cases).
  B9 fixed retrieval grading — the *third* surface a STEM student touches. B10 fixes the first
  two, the ones that decide "is this built for me?" on day one. **Not a defer:** retrofitting
  these after the native client ships = a UI rewrite (prose-shaped note view, text-only tutor
  bubble). The whole point of doing it now is that the designer builds surfaces that already hold
  math. Root cause both share: **the synthesis prompt has no worked-example/math vocabulary at
  all** (it's humanities-tuned — "prose for explanations"), and the tutor never sees the subject.
  Scope:
  1. **Content picks form — always. The family is a *prior*, not a gate.** The synthesizer is
     taught, for **every** note regardless of family, to render **math and worked examples where
     the material calls for it** and **prose where it calls for that** — one content-driven prompt,
     not a STEM branch vs. a humanities branch. So a GENERAL econ note renders its one stats
     derivation properly, and a theory-only STEM topic stays all prose. The subject family adds a
     **one-line lean** ("this topic is likely STEM — expect many worked steps / likely humanities —
     expect mostly prose") that biases the default, and drives the client `render` hint — it never
     *forbids* a worked example in a humanities note nor *forces* one in a prose-only STEM topic.
     Why prior not gate: a gate makes classification a single point of failure (a misclassified
     topic renders with the wrong whole-note shape — now a *visible* failure, where pre-B10 a wrong
     family only softly skewed retrieval mix), and it can't handle the common mixed case. **A real
     note is usually a mix** — theory prose *and* worked calculations in one topic — and may be
     all-prose or all-worked. Failure runs both ways: prose-flattening a derivation **and**
     inflating a two-line definition into a fake worked example. Math is LaTeX (same `$…$`
     convention as B8/B9). **Code and tables ride on Markdown** — the same prompt must keep code in
     fenced blocks and tabular data in Markdown tables (don't prose-ify an algorithm or a
     comparison table); no new rendering work, they're free in any Markdown renderer and degrade
     gracefully. Incremental-merge must preserve existing worked examples *and* prose.
  2. **Classify the family early enough to lean the prompt.** Today family is inferred *from the
     finished note* ([`knowledge_synthesizer.py`](../backend/app/services/knowledge_synthesizer.py))
     — too late to bias synthesis. Move it to a cheap pre-classification from the raw chunks (or
     first-N) **before** `_synthesize_body`, so the one-line lean + render hint are available;
     keep the **user-override lock** (a manual family set skips classification and wins across
     re-synthesis). Note this is only a *lean* now, so a wrong guess degrades gracefully to
     content-driven form — the stakes are lower than under a gate, which is the point.
  3. **Subject-aware tutor.** [`study_agent.py`](../backend/app/services/study_agent.py) gets the
     topic's family/profile in its system prompt (when opened on a topic; course-wide chat stays
     neutral): STEM ⇒ render math and **work the example** rather than describe it. Same principle
     — a lean, not a straitjacket; content still leads. Distinct from the existing tone/emoji/style
     *persona* knobs — subject shape is orthogonal to personality.
  **Client note:** the note/tutor surfaces are **always math-capable** (any note may quote a
  formula); `render` is a layout-density hint, not a capability switch.
  **Green when:** a STEM topic's note renders worked examples/derivations with math where the
  material has them and prose where it doesn't; a GENERAL note containing a calculation renders
  that calculation properly (proves it's content-driven, not gated); a prose-only topic (STEM or
  not) stays prose; family is classified before the note body and the user override still wins;
  the tutor renders math and works examples on a STEM topic; a pure-prose humanities note + tutor
  reply are unchanged (no regression); incremental re-synthesis preserves existing worked examples
  and prose. **Excluded (stays post-launch):** SymPy/symbolic method grading — B10 is what STEM
  students *read and talk to*, not automated derivation-checking.

- [x] **B12 · Structure-first synthesis — the note becomes a study surface, not a comprehensive doc.** *(added 2026-07-21; done 2026-07-21, 338 tests, +8)*
  **Built:** prompt-level, no migration — same shape as B10. (1) Extended the shared `_FORM_RULES`
  with a **STRUCTURE BEFORE PROSE** block encoding the owner steer as *principle, not a mapping
  table*: the **objective** (lift every core AT A GLANCE, no connective filler), the **kill-the-
  default** line (prose is the fallback prior and *that fallback is the bug* — no default to fall
  back on; derive each section's shape from what its material is doing), and a **self-check** the
  model runs on its own output ("cores pullable at a glance? any pure-connective sentence?").
  Forms (itemised labelled entries, grouped/ordered lists, the rare table, prose-for-flow) are
  framed as *outcomes, illustrative not prescriptive* — no `content-type → form` arrows. Both-ways
  guard kept: prose where an idea needs FLOW, never force a table onto non-tabular ideas ("same bug
  as under-structuring"). Because `_FORM_RULES` is shared, the discipline rides the incremental
  merge too. (2) Retuned `_full_prompt`'s framing from "study ONLY this document and have
  everything" → the **two-layer model**: raw uploads are the verbatim *source layer* (the archive),
  the note is the *studiable structure* on top, freed to go lean; rules now "lead each section with
  its recallable core; cut connective filler," length matches *ideas* not word count. B10's
  math/worked-example `_FORM_RULES` and family lean untouched (regression-pinned).
  **Tests (`tests/test_structure_synthesis.py`, +8, reuses the B10 `_LLM` harness):** old
  comprehensive-dump framing gone · two-layer source framing present · structure principle
  (objective + kill-default + self-check) present · leads-with-recallable-core · *not* a
  content-type mapping (forbidden arrows absent, principle present) · over-structuring guard
  (needs-FLOW + no-forced-table) · **B10 math/LaTeX/lean unchanged** · structure rules ride the
  incremental prompt.
  **Owner note — behavioural green-when is a live-LLM eval, not in this suite.** All LLM boundaries
  are monkeypatched, so these tests pin the *prompt contract* (mirroring B10's approach). The true
  "archaeology source → comparison table, narrative → prose, concepts come out sharper" check needs
  a real model; treat the prompt as the tunable and, if a live run still narrates, strengthen the
  anti-default line — never add a mapping table. **Client seam still owed (C2):** a readable
  "show me the original" source-read view — data exists (chunks), UI is not this item.
  **Not migrated** — prompt-only.
  <details><summary>Original build spec (for reference)</summary>

  B10 taught the synthesis prompt the *math* half of "form follows content" (LaTeX, worked
  examples, code, and tables it finds *already tabular*). This is the **humanities half** — the
  gap found by dogfooding v1 on an all-prose topic (Archaeological Evidence in Nigeria: five
  sites each with date / materials / significance, four equipment categories — a comparison
  table and two taxonomies, narrated as a wall of prose). **The failure is family-agnostic:**
  a prose-shaped note doesn't stick and can't be practised — you reconstruct the *paragraph*
  instead of the *idea*. And it isn't only a reading problem: **concepts are extracted *from*
  the note** (`_extract_metadata`), so a blurry prose note yields blurry concepts, and
  retrieval / quiz / brain-dump run on those concepts. **The note is the root of the tree — its
  shape propagates to the whole engine.** One lever fixes reading *and* retrieval.
  **The reframe (owner call 2026-07-21): comprehensive ≠ studiable.** The current `_full_prompt`
  tells the model "this covers the topic completely; a student should study ONLY this document
  and have everything" — that instruction *is* the bug; it pushes toward exhaustive prose.
  Resolved by the **two-layer model**: the **source layer** (raw transcriptions / chunks —
  already stored) is the comprehensive verbatim archive *and* the tutor's RAG fuel; the **note**
  is the *studiable structure* on top. The note need not hoard everything — the chunks are the
  archive — so it's freed to go structure-first.
  Scope:
  1. **Let form follow what each section's material is *doing* — by principle, not a lookup table.**
     Do **not** hand the synthesizer a fixed `content-type → form` mapping (comparison→table,
     taxonomy→list…); that just swaps the prose bias for a *menu* bias and can't fit material we
     didn't foresee. Encode three things instead, none of them a form: **(a) the objective** — a
     student must be able to lift every core idea *at a glance*, with no connective filler to read
     past; **(b) kill the default** — prose is the model's fallback prior and *that fallback is the
     bug*; tell it to derive each section's shape from what the material is doing, with no default
     to fall back on; **(c) a self-check** it runs on its own output — "can the cores be pulled from
     this section at a glance? is any sentence pure connective tissue?" The concrete forms —
     itemised labelled entries, grouped / ordered lists, the occasional table, prose where an idea
     genuinely needs *flow* — are **outcomes the model arrives at, illustrative not prescriptive**,
     never a rulebook applied mechanically (a table is rarely the best fit — dense, high-level — so
     it isn't a reflex either; owner steer 2026-07-21). Each section **leads with its recallable
     core.** **The real contract is the tests, not the prompt wording** (Green-when below): the
     archaeology-style topic must gain structure *and* a narrative topic must stay prose — those two
     pin the behaviour; the prompt only has to be a sound principle.
  2. **Retune `_full_prompt`'s "comprehensive doc" framing to "studiable structure."** Drop
     "study ONLY this document and have everything" (the source layer holds the complete
     record); the note's job is the shape you'd actually study from, prose only where an idea
     needs flow. **Keep B10's `_FORM_RULES` intact — this extends it, doesn't replace it.**
  3. **Failure runs both ways — don't over-structure.** A genuinely narrative source (an
     argument, a historical account with causal flow) stays prose; don't force a table onto
     ideas that aren't tabular, don't shred a flowing explanation into disconnected bullets.
     Same discipline as B10's "don't invent structure the material lacks," pointed the other way.
  **Client note:** the **source layer must be reachable as a readable view** — "show me the
  original / read it as it was" (widen C2's "says who?" X-ray into a source-read affordance).
  That's the guarantee that lets the note go lean without anyone losing the verbatim.
  **Green when:** an entity-attribute prose source (the archaeology case) renders as a comparison
  table + grouped lists, not a prose wall; each section leads with its recallable core; a
  genuinely narrative topic stays prose (no forced tables); B10's math / worked-example behaviour
  is unchanged; extracted concepts come out sharper off the restructured note. **No migration** —
  prompt-level, same as B10.
  </details>

- [x] **B13 · Generative-prompt quality sweep — principle over prescription, system-wide.** *(added 2026-07-21; done 2026-07-22, 349 tests, +11 across both phases)*
  B12's insight generalises: it's not a note-synthesis fix, it's a **prompt-design principle** the
  whole system should follow (now invariant #12). The live evidence is the **audio** — users
  reported it's *repetitive* — which is the same root as the prose-wall (an over-prescriptive prompt
  → mechanical output), just a different symptom (monotony instead of wrong-shape). Sweep every
  **generative** prompt — one a human reads or hears — and refit it to *objective + judgment +
  self-check*, killing the templated default instead of naming the alternative.
  **In scope (generative):** `audio_generator.py` (**do first — the known live complaint**),
  `study_agent.py` (tutor), `question_generator.py` / `retrieval/quiz_mode.py`, `retrieval/ramble_mode.py`
  / `teach_mode.py`, `retrieval/recap.py`, `grader.py` (feedback rationale), `fact_checker.py`,
  `research_generator.py`, `knowledge_synthesizer.py` (note = B12 + key-points phrasing).
  **Explicitly OUT of scope (structured/control — leave rigid, determinism is the feature):**
  `_classify_family`, `_extract_metadata` (JSON), closed-vocab self-grade, `ocr_cleaner.py`,
  `vision_transcribe.py`, `voice/lane.py` protocol frames. Loosening these breaks the parser — the
  guard-rail test must prove they're untouched.
  **Audio has a second failure notes don't:** *inter*-lesson sameness — each script is generated
  from an identical scaffold with no awareness of the others, so they all open the same way. The
  anti-template principle fixes the *intra*-script formula; add a distinct "vary the opening / don't
  reach for the same frame" nudge for the *inter*-script repetition.
  **Green when:** two independently-generated audio scripts don't share an opening or section
  skeleton; a tutor reply and a piece of feedback don't read as filled-in templates; the note (B12)
  and questions still pass their own Green-whens; **and the structured/control prompts above produce
  byte-identical output to before (the guard).** Prompt-level, **no migration**. Can phase — audio
  first (ship the fix for the actual complaint), the rest as polish. Not a hard launch blocker
  except audio, which is a live quality regression.
  - [x] **Phase 1 · audio** *(done 2026-07-21, 344 tests, +6)* — the live regression, shipped.
    `audio_generator.generate_script`: replaced the fixed HOOK→per-concept-loop→transition-menu→
    CLOSING scaffold (the thing that made every lesson sound alike) with *objective + judgment +
    self-check* — "make THIS material stick", "no fixed arc to fill in", "memory is built by
    retrieval not exposure", and a closing self-check ("does the opening come from THIS topic, or
    could it head any lesson? any stretch on autopilot?"). Added the **inter-script** nudge notes
    don't need ("one of many lessons… don't open two different topics the same way"). Raised
    `audio_script` temperature 0.5 → 0.8 (low temp was itself part of the sameness). **Incidental
    bug fixed:** dropped the `[EMPHASIS]` token — `generate_audio` only strips `[PAUSE]`, so
    `[EMPHASIS]` was reaching TTS and being spoken aloud literally; `[PAUSE]` (machine-parsed) kept.
    **Tests (`tests/test_audio_script.py`, +6):** killed-scaffold absent · principle+self-check
    present · inter-script variety nudge · `[PAUSE]` kept / `[EMPHASIS]` gone · temp ≥ 0.7 · **guard:
    the control prompt `_classify_prompt` stays rigid (one-word contract intact, no generative
    markers bled in).** Behavioural green-when (two real scripts share no opening/skeleton) is a
    live-LLM eval, not in the deterministic suite. No migration.
  - [x] **Phase 2 · the rest (polish)** *(done 2026-07-22, +5 tests → 349)* — swept the remaining
    generative surfaces, and — the judgment call — **left the structured-judgment prompts rigid on
    purpose** (loosening them was the wrong move, not out-of-time). What changed:
    - **`research_generator` — the real template offender.** It forced every pre-class doc through a
      mandatory 5-section skeleton (Core Concepts / Historical Context / Key Points / Misconceptions
      / Connections) regardless of material — a padded-headings machine. Replaced with the objective
      ("walk into class oriented"), *material decides which sections exist — no fixed skeleton*, and a
      self-check ("is every section carrying weight, or there because overviews *usually* have it?").
      JSON envelope (`research_content` / `key_concepts`) untouched.
    - **`question_generator` — anti-sameness + self-check, JSON schema untouched.** Already
      principle-driven ("good/bad questions"); added "VARY THE FRAMING — don't cast every question
      the same mould" and a "N distinct probes, or N fills of one template?" self-check. This is the
      *questions still pass their Green-when* clause.
    - **`study_agent` tutor — anti-template line.** Already largely principled; added "answer THIS
      question, not a template — two different questions shouldn't come back shaped identically",
      orthogonal to the persona axis (persona test still green).
    - **`grader` encouragement — inter-instance variety (the audio lesson, applied to feedback).**
      A per-question surface a student sees many times in a row, so it had audio's sameness risk:
      added "vary it — don't hand them the same sentence shape every time ('Great job on X, but
      remember Y')".
    - **Left rigid, by design (structured judgment — consistency IS the feature):** the grading
      rubric + essay grading, `recap` / `teach` / `ramble` evaluation, `fact_checker` verification.
      Their human-read feedback fields are *already* anti-generic ("not just 'good job'"); loosening
      a scoring rubric would destabilise grade consistency. The **guard test proves it** — the
      grading prompt still carries its SCORING GUIDE + JSON contract and none of the generative
      markers bled in. (`knowledge_synthesizer` note = B12; its key-points come from the structured
      `_extract_metadata`, which stays rigid — OUT of scope.)
    - **Tests (`tests/test_generative_prompts.py`, +5):** research skeleton gone / material-driven /
      self-check / JSON intact · question variety + self-check + JSON contract · tutor anti-template +
      persona intact · encouragement variety · **grading-rubric guard (rigid, unbled).** Behavioural
      green-whens (two real research docs differ in shape; ten encouragements don't rhyme) are
      live-LLM evals. No migration.

### Phase C — needs the native client (Phase 5 designs)

> **Backend-status audit (2026-07-13, end of Phase B)** — each item annotated with what the
> server already provides vs. what's genuinely missing, so the Phase C builder doesn't
> re-derive it. Per-item traps live in build-guide §4 ("Phase C — backend seams & traps").

- [ ] **C1 · Home / one-card entry** (doorway-not-dashboard; review-default hero).
  *Backend done:* `GET /api/retrieval/next-action` (B3) already returns the one card
  (kind/mode/scope/reason/estimate). Home is client assembly over it — don't add a second selector.
- [ ] **C2 · Active-surface note canvas** (note↔concept linking = *launch into retrieval*, rendered
  math, "says who?" X-ray). **Simplicity call (2026-07-21):** the linking exists to let a user
  *retrieve on a paragraph right there* — **not** to colour/tint terms by mastery. **No ambient
  mastery heat-map on the note; keep the reading view clean.**
  *Backend GAP + escalation:* the note prose is **not span-linked** to concepts or contributors —
  `TopicKnowledge.concepts` is a flat JSONB list; concepts carry `source_chunk_ids` (chunk
  provenance) but attribution is **topic-level by design** (build-guide §5). Claim-level "says
  who?" changes the attribution grain → **§7 escalation, not a solo build.** Note↔concept span
  anchoring belongs in the synthesis output contract (A4's pipeline) — decide there, not ad hoc.
- [ ] **C3 · Progress — a quiet standalone surface** (what's fading / what's solid; calibration
  surfaced when needed). **Amended 2026-07-21 (owner call):** progress is its *own simple surface*,
  **decoupled from the note** — the earlier "note lit by mastery IS the progress map" is dropped for
  simplicity (no ambient colouring; see C2 + system-spec §11). Same data, plainer surface.
  *Backend GAP, cleanly buildable ahead:* no endpoint exposes per-concept mastery topic-scoped
  (`progress.py` only has coarse `UserProgress` averages). All data exists — `ConceptState`
  (stability/due/reps/lapses/last_grade) + concepts-by-topic; calibration is derivable from the
  attempt log (`predicted_confidence` vs `outcome_score`). Pure read endpoint, **no schema change**.
  *(The backend read endpoint is unchanged by the simplification — this is purely how the client
  surfaces it.)*
- [ ] **C4 · Capture dump UX** (drag/snap/record → confirm the proposed topic structure).
  *Verify before assuming:* `api/capture.py` (A2) exists — confirm its propose→confirm contract
  actually matches the UX (a dump must return a *proposal* the user can amend, not auto-commit).
- [ ] **C5 · Offline local store + background sync** (cache-first; boundary + 10–15 min poll).
  *Backend done* (B6, `/api/sync/*`). Client owns the local store, poll cadence, and replay queue
  (client-generated `client_event_id` per attempt; only quiz/pretest may push).
- [ ] **C6 · Voice conversational UI** (co-presence, active-listen seams).
  *Backend done* (B5, `WS /ws/voice/{course_id}`; frame vocabulary in
  `services/voice/protocol.py`). Client owns STT, VAD endpointing (`speech_final`), barge-in
  frames, audio playback, mic-permission states. Lane ships dark: `ENABLE_VOICE_LANE=false`.
- [ ] **C7 · Onboarding flow** (gap-first pretest opening; hybrid demo-while-processing).
  *Backend done:* composition over existing pretest mode + `/next-action` + capture; no new
  server work expected.
- [ ] **C8 · Contribution visibility** (§6 — "N built this note," no leaderboard).
  *Small backend seam:* the B1 substrate already holds the data (consume events + attempt log;
  `recognition.resolve_beneficiaries`). Needs only a small read endpoint for the count — keep it
  aggregate ("N built this"), never ranked (no-leaderboard is a product invariant).

### Phase D — Launch readiness: ops + compliance (added 2026-07-17; parallel to Phase C)

> All backend, all small, none blocked by the native client. The non-code compliance
> checklist (store forms, privacy labels, purpose strings, legal docs, NDPA) lives in
> [`launch-readiness.md`](./launch-readiness.md) — this queue carries only the buildable
> items. **Locked decisions:** iOS auth is **phone-only** (no Google on iOS ⇒ no
> Sign-in-with-Apple obligation); report mechanism = report → auto-quarantine → owner
> reviews (launch-scale moderation); launch is free ⇒ IAP/Play Billing deferred.

- [ ] **D1 · Rate limiting.** Redis-counter limiter (we already run Redis — no new dep beyond a
  thin helper). **OTP endpoints first and strictest** (per-phone AND per-IP on register/resend;
  cooldown + daily cap — OTP pumping fraud costs real money) and verify-OTP attempt caps
  (brute-force). Generous defaults on everything else (per-user on authed routes, per-IP on
  public). 429 + `Retry-After`. **Green when:** OTP flood from one phone/IP is throttled in
  tests; normal auth flows unaffected; limits configurable via settings.
- [ ] **D2 · Observability.** (a) **Sentry** — FastAPI integration + explicit capture in the
  worker loop's `_handle_failure` (a dead-lettered job must page, not just log). (b) **Ops
  endpoint** — queue depths, DLQ counts, oldest-job age (auth-gated). (c) **LLM cost telemetry** —
  one log line in `call_llm`/`call_llm_stream`: task, model, tokens in/out (the single call site
  makes this trivial — do NOT scatter it). (d) **Log hygiene** — JSON logs in prod, request-ID
  correlation, and a redaction helper: **phones and OTPs never appear in logs.** **Green when:**
  a forced worker exception lands in Sentry; ops endpoint reports a seeded DLQ job; a `call_llm`
  call logs task+tokens; a log line containing a phone number is redacted in tests.
- [ ] **D3 · Account deletion.** `DELETE /api/auth/me` (re-auth/OTP-confirmed) implementing the
  locked design: user row purged, attempts **de-identified** (not destroyed — the shared
  substrate survives), contributed resources/notes stay but de-attributed, personal state
  (ConceptState, notifications, enrollments, contacts hashes) hard-deleted. Store requirement
  (Apple 5.1.1(v)) + NDPA/GDPR right. **Green when:** post-deletion, no query can link surviving
  rows to the identity; login with the old phone starts fresh; tests prove de-identification.
- [ ] **D4 · Review-mode bypass.** Store reviewers can't receive WhatsApp OTPs. Flag-gated
  allowlist of test phone numbers with a fixed OTP (env-configured, off by default, never valid
  for real numbers). **Green when:** allowlisted phone + fixed code logs in when the flag is on;
  the fixed code fails for any non-allowlisted phone; flag off ⇒ behaviour identical to prod.
- [ ] **D5 · Report / abuse mechanism.** UGC store requirement (Apple 1.2 / Play UGC + AI-content
  policies). Minimum honest design that fits ownerless governance: `POST /api/reports` on a
  resource / note / AI output → **reuse the quarantine machinery** (reported content held out of
  the shared surface, uploader-only, like the merge gate) → owner reviews (launch-scale process)
  → release or remove. Reporter never sees the outcome loop (no moderation theatre); repeat-abuse
  = per-user block list (blocks their *future* content from your shared surfaces). **Green when:**
  a report quarantines the target + notifies nothing publicly; release/remove paths work; block
  hides a user's future uploads from the blocker's view; tests green.

### Explicitly deferred past launch (🔮)
Video embed · live study rooms / competitive quizzing · coordination-mode polish · language
subject profile · timing/sleep-aware delivery · speech-emotion calibration · gift-a-connection
+ pricing infra (launch is free) · automated STEM method-grading (self-graded ships first).

- **B11 · Figure / diagram preservation *(tracked deferral — the last real STEM-parity piece)*.**
  Rendering has two axes: *text forms* (prose + math — B10; code/tables free on Markdown) and
  *non-text content* — **figures, diagrams, plots, labelled schematics** — which no amount of
  prose or LaTeX can reconstruct (the diagram *is* the content). Today the capture pipeline is
  **text-only**: [`file_processor.py`](../backend/app/services/file_processor.py) OCRs PDF pages
  and transcribes images **to text**, so a source figure is flattened or lost before synthesis
  ever sees it. This is a **capture problem, not a synthesis one** — you can't render what
  ingestion threw away. Real work: detect/extract figures at ingestion, store them (Cloudinary),
  and reference them inline in the note so synthesis can place them. **Spec-vs-reality flag:**
  system-spec §3 and product-map §1 already *promise* "figures preserved and referenced, not
  flattened" — so this is a promise currently unmet, not a new idea; the native client should be
  **designed to hold inline figures** even while backend delivery is deferred, so it's not a UI
  retrofit later (same reasoning as B10). Below this: chemical structures/SMILES, music notation,
  circuit schematics as first-class — genuine defer-and-maybe-never; user-photo capture covers
  them well enough.

- **Quiz generation — in-flight request coalescing *(deferred, owner call 2026-07-21)*.** The
  shipped "already exists" sync catches a *finished* matching quiz; this is its runtime sibling —
  when a user hits generate and a matching generation is **already in progress**, subscribe them to
  that job instead of spawning a duplicate (both wait on one result). Fits the model cleanly: a
  Redis **in-flight registry keyed on the params signature** (reuse the sync's signature), second
  requester attaches (pub/sub or polls the job id), one worker run serves all. **The gating
  question a builder must answer first:** are generated quizzes *shared* or *per-user personalised*
  (mastery-weighted / concept-selected)? If personalised, two requests rarely match the same
  signature, so coalescing almost never fires and isn't worth the machinery — it only pays off if
  identical preselected params yield an identical quiz. Decide that before building.
- **Model tiering / specialised providers *(deferred, owner call 2026-07-21)*.** Route each
  workflow to the best-fit model instead of one provider everywhere — specialised engines for audio
  transcription, voice streams, embeddings, plus cost-tiering cheap vs. reasoning-heavy tasks.
  **Low-risk defer: the seam already exists** — invariant #5 (one LLM call site, `services/llm.py`,
  task→provider map) + A1's fast/small tier mean this is **routing/config expansion, not a
  structural change**; specialised providers get added to the map without touching any service or
  worker. Nothing else has to move for it to land later. (Audio transcription is Whisper today;
  voice streams are B5 — those are the first specialised swaps when this is picked up.)

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
