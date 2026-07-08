# NotesOS v2 — Backend Redesign Plan

> **Living document.** The execution plan for rebuilding the NotesOS backend on the
> emergent-set architecture. This is the *what / how / status*; the *why* lives in
> [`NotesOS_Architecture_NextPhase.md`](../NotesOS_Architecture_NextPhase.md)
> (canonical on conflict) and [`NotesOS—Product_Brief.md`](../NotesOS—Product_Brief.md).
>
> Last updated: 2026-07-05.

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
dynamic pricing scaffolding (present, not pushed).

## Current v2 schema (new/changed)

- `schools` (id, name, normalized_name unique, country, aliases jsonb)
- `terms` (id, user_id, division_type enum, division_value, study_level, label; unique per user+label)
- `users` += school_id, program, entry_year, phone
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
