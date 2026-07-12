# NotesOS — Architecture & Build Guide (for implementing agents)

> **Read this before you touch a queue item.** The other docs tell you *what* to build; this one
> is the **tacit layer** — the invariants you must not break, how the codebase actually behaves in
> practice, the per-item traps and what to reuse, and **when to escalate to the architect instead
> of deciding solo.** It won't repeat the specs; it's the stuff that isn't written down anywhere
> else and that will otherwise be re-derived (often wrongly).
>
> **Where truth lives:** `NotesOS_Architecture_NextPhase.md` (canonical — wins on any conflict) ·
> `docs/product-map.md` (feature intent + every locked decision) · `docs/system-spec.md` (behaviour
> contract, written for the client designer but accurate for you too) · `docs/v2-redesign-plan.md`
> (the build queue + each item's "Green when" acceptance bar) · `CLAUDE.md` (project structure +
> conventions, auto-loaded). This guide is *implementation guidance*, not a source of product truth.
>
> Last updated: 2026-07-12.

---

## 1. The non-negotiable invariants

Breaking one of these doesn't cause a bug — it breaks the architecture. If a task seems to require
it, **stop and escalate** (§7).

1. **The attempt log is append-only.** `RetrievalAttempt` rows are only ever *added* — never
   mutated, never deleted. `ConceptState` (FSRS) is a **materialized view derivable from the log**.
   This is load-bearing for offline sync (union-merge) *and* progress. Never introduce
   per-user state that can't be re-derived by replaying the log.
2. **Derive before you store.** Sessions (15-min idle gap), calibration (`outcome − predicted`),
   the classmate set (enrollment overlap), discovery feeds — all **query-only over existing
   tables, no new table**. Add a column/table only when derivation is genuinely impossible. A
   surprising number of "features" are queries, not schema.
3. **No container entities.** There is no `Class` / `Cohort` / `Semester`-as-parent. The set is
   **emergent** from `course_enrollments` overlap. `Term` is a *label*, not a parent node. Don't
   add a stored group object.
4. **Governance is ownerless.** No roles, admins, moderators, approval queues, permission tiers.
   Quality is held by the Merge Agent gate + corroboration + attribution ("name on it"). Don't add
   a human-authority surface.
5. **One LLM call site.** All completions go through `services/llm.py` (`call_llm`, and
   `call_llm_stream` once A1 lands). Task→provider routing lives there. **Never** scatter a raw
   provider call into a service or worker.
6. **Session discipline.** `get_db()` (FastAPI dep) in routes; `worker_session()` (context
   manager) in workers. **Never mix them.** All DB access is `async` and `await`ed — no sync
   SQLAlchemy.
7. **Modes are plugins over one Protocol** (`generate` / `evaluate` / `subject_weight`). Adding a
   mode = a new file + one `register()` line. **Never special-case a mode inside the engine.**
8. **Attribution is topic-level, on purpose.** Recognition resolves `concept.topic_id →
   non-quarantined resources → uploaded_by`. Synthesis blends all of a topic's chunks into one
   document, so there is **no per-concept provenance** to be had. Don't fake per-concept precision.
9. **Immutability (coding style).** Return new objects; never mutate inputs in place.
10. **The proximity check never forces a merge.** Every check ends in an *offer*; "make my own"
    stays live.
11. **No hand-written migrations.** Models are truth → `alembic revision --autogenerate`. Extensions
    go in `init_db()`; seed/reference data in `scripts/`. (The owner runs migrations.)

---

## 2. How the codebase actually works (the practical map)

File pointers are anchors — **verify against current code** before relying on a specific line; this
reflects the state as of the design sessions, and memory drifts.

- **LLM — `services/llm.py`.** Single call site. **Blocking today** (reads the full completion;
  A1 adds a streaming sibling). Task→provider map routes each logical task to openai (`gpt-4o-mini`)
  or deepseek (`deepseek-chat`); overridable via `LLM_<TASK>` env. There is **no fast/small tier
  yet** — A1 adds one. `VISION_MODEL` = gpt-4o for image OCR.
- **Synthesis — `services/knowledge_synthesizer.py`.** Produces the consolidated note. **Today it
  FULL-REBUILDS**: fetches *all* non-quarantined chunks for the topic, caps context ~80k chars,
  one LLM call, upserts `TopicKnowledge` by `topic_id`. This is the write-amplification cost bomb
  **A4 replaces with incremental append-merge.** Runs inside `knowledge_worker`, *after* the
  merge-gate.
- **Retrieval engine — `models/retrieval.py` + `services/retrieval/`.** Substrate: `Concept` /
  `ConceptState` / `RetrievalAttempt`. `scheduler.py` is the **only** file that imports fsrs.
  `modes.py` = the Protocol + `Challenge`/`Outcome`/`ModeContext` dataclasses + shared
  `score_to_grade`. `engine.py` = mode-agnostic core (`select_concepts` / `record_attempt` /
  `run_once`). `quiz/ramble/teach/pretest_mode.py` = plugins; `registry.py` = key→mode. `api/
  retrieval.py` = `/next` → `/attempt` (challenge cached in Redis by id between the two) + `/modes`;
  calibration is derived in the response. `recognition.py` = **dormant seam** (topic-level, gated
  behind `ENABLE_RECOGNITION=false`).
- **Workers — `run_workers.py` (`asyncio.gather`) + `workers/`.** All drain Redis queues via the
  shared `run_worker_loop` (retry / backoff / dead-letter / orphan-recovery) using `worker_session()`.
  The **machine (`base.py`) is correct — don't touch it.** The **roster is a v1 inheritance** — see
  §2a for keep/retire/add. **The realtime voice lane (B5) is a NEW pipeline — do not build it on
  these workers.**
- **Capture pipeline.** upload → `transcription_worker` (vision / `file_processor`) → enqueue
  `chunking` → `chunking_worker` (chunks + Voyage embeddings) → `knowledge_worker` (merge-gate →
  synthesis). Accepted types are allow-listed in `api/resources.py` (images + docs today; **A2 adds
  audio**). `transcription.py` (Whisper) exists but is currently wired **only to grade voice
  answers** — A2 exposes it as an *ingestion* path (the front door of this pipeline), **not** a
  grading feeder.
- **DB — `database.py`.** Async engine, `pool_size=2, max_overflow=3` **per process** (each worker/
  API process owns its pool). `init_db()` creates tables + the `vector` / `pg_trgm` extensions.
- **Cache — Redis.** Keys follow `{resource}:{id}`; invalidate with `cache.delete(key)` in the
  handler *after* the DB commit on any write.
- **Realtime — Redis pub/sub → WebSocket** (`course_updates` channel, one connection per course).
  Events include `processing_status`, `grading:complete`, note/knowledge updates, presence.

---

## 2a. Workers: keep / retire / add (do NOT cargo-cult the v1 roster)

The seven workers in `run_workers.py` were built for v1's feature set. The **loop machinery is
right**; the **set is not**. Against v2, the roster splits three ways. Verify against current code,
but this is the intended target:

**Keep — core to v2 (two change under the hood):**

| Worker | Status in v2 |
|---|---|
| `chunking` | Unchanged — capture-pipeline spine. |
| `knowledge` | Same worker, **A4 rewrites the guts** full-rebuild → incremental append-merge. |
| `audio` | Listen's engine. Emits **N rotating variants** per topic, not one (locked design). |
| `transcription` | **A2 promotes it** to a first-class *ingestion* front door (feeds chunking), not a grading feeder. |

**Retire — superseded by the retrieval engine (they have no v2 caller):**

| Worker | Why it dies |
|---|---|
| `test_generation` | v2 generates challenges **on demand** in `POST /retrieval/next` via `mode.generate()`. The batch pre-gen model is gone. |
| `grading` | v2 evaluates **synchronously** in `POST /retrieval/attempt` via `mode.evaluate()`. See the voice decision below. |

**Parked — deferred, leave dormant:** `fact_check` (flag-gated, not a live worker).

**Add — for the launch queue:**

- **B2 notifications / daily digest** — the habit engine (decay-driven "you're about to forget X",
  next-best-action). This is a **new *kind* of worker: periodic, not reactive.** `base.py` only knows
  how to drain a queue when an event arrives; the digest must fire on a schedule per user regardless
  of events. **Do not bolt `sleep(86400)` onto the reactive loop.** Add **APScheduler** (async-native,
  lightweight) as the periodic tick alongside the queue workers. See §5 for why not Celery.
- **B1 recognition delivery** — the `recognition.py` seam already computes beneficiaries live but
  delivers nothing (flag off). When it goes live it **folds into the notifications worker** (aggregate
  + push); it is not a standalone worker.

> **LOCKED — voice transcription is client-side.** A retrieval `/attempt` evaluates **synchronously**
> and returns `outcome + calibration` in one response. That is incompatible with server-side Whisper
> (can't transcribe-then-eval in one request). Resolution: **the client transcribes; `/attempt` only
> ever receives text.** This keeps the retrieval contract synchronous and fast, retires the `grading`
> worker, and makes voice purely a *capture* concern (`transcription` worker), never a *grading* one.
> Do not add an async voice-eval path to retrieval.

---

## 3. Testing & process (patterns + the gotchas that will bite you)

- **Real Postgres** (`notesos_test`), schema built from models, `TRUNCATE` between tests; the
  harness creates the extensions. **TDD, 80%+**, new logic ships with tests.
- **Stub the LLM boundary, never call a real model in tests.** The pattern: subclass the mode and
  override its single private LLM method (see `StubQuizMode`). Every mode isolates its LLM call
  behind one method precisely so tests can override it — keep that discipline in new modes.
- **Redis event-loop gotcha (real, already hit).** The `redis_client` singleton binds its
  connection to whatever event loop first used it; with per-test function-scoped engines you get
  `RuntimeError: Event loop is closed`. Any test touching Redis needs the `_fresh_redis` autouse
  fixture (reset `redis_client._client = None` before, `await ...aclose()` after). Reuse it.
- **Migrations:** after a model change, `alembic revision --autogenerate` — then hand the migration
  to the owner to run. Don't edit tables by hand.

---

## 4. Per-item build guidance (reuse this, watch for that)

- **A0 · Auth (phone-primary).** `phone` → required + unique + OTP-verified; `email` → nullable.
  **Expect to rewrite the auth test fixtures** — they assume email-primary. Make the **OTP provider
  swappable and stubbed in tests** (owner picks WhatsApp vs SMS; don't block on it). Google OAuth
  stays but the user still **enters + OTP-verifies a phone** — never infer it from Google. The phone
  field that contact discovery (later) hashes on lands here.
- **A1 · Streaming + tiering.** ✅ *done (2026-07-12).* `call_llm_stream()` + tiering (task→(provider,
  model), `fast|standard|heavy`, per-task `LLM_<TASK>` override) live in `services/llm.py`; SSE on
  the **tutor** (`POST /api/study/ask/stream`). **Streaming coverage is deliberately tutor-only** —
  it's the only free-prose surface. The rest are **structured-JSON** (synthesis, question-gen,
  research, grading — must parse the whole blob) or **record-bound** (retrieval `/next` + `/attempt`
  parse the grade *before* writing the append-only attempt). Do **not** bolt token-streaming onto
  those — partial JSON is un-renderable and it breaks the record flow. Deferred plan below (A4) and
  in §5.
- **A2 · Capture (give it its own short plan before diving — it's the meatiest).** Three pieces:
  *(a) audio ingestion* — add audio to the accepted types + a resource kind, enqueue
  `transcription` → `chunking` (reuse `transcription.py`); *(b) dump→auto-organize* — Voyage
  embeddings to cluster + an LLM to classify a bulk upload into topics; *(c) outline scaffold* —
  parse a syllabus into `Topic` rows, then **classify** incoming files into those known buckets
  (the reliable path) vs **cluster-and-propose** when there's no outline. Honor the **two add-paths**
  (course-level bulk → organize; topic-level direct → straight in, no classify). Preserve figures,
  don't flatten. Reuse the proximity-check *instinct* for slotting into existing topics.
- **A3 · Session + Recap.** Session = a **query** over `RetrievalAttempt` ordered by time, split on
  a ≥15-min gap — **no session table.** Recap = a mode that generates over **many** concepts (the
  set the last session touched) and grades **one** response into an **attempt-per-concept.** This
  *stretches* the Protocol (`generate(concept)` → one attempt) in the many-concepts/one-turn
  direction — the orthogonal stretch to multi-turn. Keep every attempt append-only.
- **A4 · Incremental synthesis.** Replace the full-rebuild with **append-merge** into the existing
  note. The merge must still **reconcile/dedupe** and **respect the quarantine gate** (never merge a
  quarantined resource). Debounce bursty uploads (one synth per burst, not per file). "What changed"
  should be derivable. **This is the trickiest item for correctness — test the merge hard.**
  **Streaming lands here (deferred from A1):** synthesis is the home for *progressive note delivery*
  — stream the note body via `call_llm_stream` and broadcast deltas over the existing course
  WebSocket (`course_updates`), so the client watches the note write itself. It's worker-driven (no
  HTTP/SSE) and today the output is one JSON blob (`note`+`key_points`+`concepts`) parsed whole, so
  reshape the prompt to **emit the prose body first (streamable), metadata after.** Not done in A1
  because A4 rewrites this pipeline anyway — doing it earlier is throwaway.
- **B1 · Recognition live** needs the §11 attribution/consumption layer *first*; then flip
  `ENABLE_RECOGNITION`. Warmth rules (aggregate passive / warm active) before it pings anyone.
- **B3 · Next-best-action** is **one selector**, shared by the home (pull) and the decay digest
  (push). Don't build two.
- **B4 · Subject profiles.** `SubjectFamily = STEM · LANGUAGE · HUMANITIES · GENERAL`; **infer at
  synthesis**, store `subject_family` on the Topic (overridable; concepts inherit); centralize the
  family→mode affinity in one profile map; **replace the loose `subject_weight` strings** (they're a
  placeholder — don't build on them).
- **B5 · Realtime voice** = a NEW streaming pipeline (STT + LLM + TTS overlapped, VAD endpointing,
  barge-in); the grade is emitted **off-turn by the same streaming call**. Not the batch workers.
- **B6 · Offline sync** = invalidation endpoints (`last_synced_at` → changed IDs) + append-only
  event push; event-sourced (derive `ConceptState` from the pushed log).

---

## 5. Rationale that constrains (do NOT "fix" these — they're deliberate)

- **Single-shot modes** are a deliberate floor, not a limitation. Multi-turn Socratic is a *designed
  future*, built as a wrapper over append-only attempts — not a Protocol change.
- **Topic-level recognition** is a data reality (synthesis blends chunks), not laziness.
- **No session table** is the derive-first philosophy, not an oversight.
- **Append-only** is the foundation of conflict-free offline sync — don't trade it for convenience.
- **The `subject_weight` strings** are a placeholder B4 replaces — don't build features on them.
- **Cost == speed.** Prefer pre-generation / caching / model-tiering / debouncing — each is
  *simultaneously* cheaper and faster. When choosing, take the double-paying option.
- **Streaming is prose-only, on purpose.** `call_llm_stream` fits free-text surfaces (the tutor).
  Structured-JSON surfaces (synthesis, question-gen, research, grading) must arrive whole, and
  retrieval `/attempt` parses the grade *before* recording the append-only attempt — so streaming
  challenge/feedback prose would change the mode `evaluate`/record flow. That's a **mode-Protocol
  change → escalate (§7)**, not a solo reshape. Synthesis's progressive-note streaming is A4's job.
- **North star: defeat the fluency illusion.** Retrieval > rereading; decay is the metric, **not
  streaks**; difficulty is a feature. Don't optimize retrieval surfaces for engagement over
  learning — that's the one thing the product refuses to do.
- **`predicted_confidence` stays optional — never make it required.** The confidence beat is a
  *contextual* UI call (asked on pretest / new / shaky, skipped on rapid review), not a data
  requirement. Attempts record with or without it; calibration is derived only when it's present.
  Don't gate `/attempt` on it or force it in a session flow.
- **Hand-rolled workers over Celery — deliberate, not NIH.** The codebase is async end-to-end
  (async SQLAlchemy, `worker_session`, `call_llm`); Celery's core is sync prefork and its async
  story is a bolt-on. We already own retry / backoff / dead-letter / orphan-recovery in `base.py`
  (~130 legible lines) on the Redis we already run. Celery would re-buy that with an opaque broker
  layer + result backend + prefork footguns (`visibility_timeout`, lost tasks). **The one thing we
  lack is periodic scheduling** — add **APScheduler** for the B2 digest tick, *not* Celery. Horizontal
  scale is already available (`BRPOPLPUSH` is multi-consumer-safe → run `run_workers.py` on N boxes).
  If we ever truly outgrow this, the async-first successors are **arq** (drop-in for `base.py`) or
  **Temporal** (durable workflows) — reach for those before Celery. Escalate before adopting any
  external task framework (§7).

---

## 6. A few cross-feature definitions to keep straight

- **Classmate** = someone you share ≥1 course with (emergent, from enrollment). **Connection** =
  a lighter tie: a discovered phone contact who's a user, or someone you invited / who invited you.
  Creation-visibility & invitation ride *connections*; join-propagation is *classmate*-scoped.
  (If a task hinges on exactly what "connection" spans, that's an architect call — §7.)
- **Topic vs Concept:** the user *consumes* topics; the engine *measures* concepts. A note is
  topic-level; mastery/FSRS is concept-level; concepts are extracted at synthesis.
- **Recognition / creation-visibility / join-propagation are one system** — consume/activity events
  on the (unbuilt) §11 substrate, aggregated + warmth-tuned. Build that event layer *once*; each is
  a policy on top. Don't build three pipelines.

---

## 7. When to come back to the architect (escalate — don't decide solo)

Escalate before building if the change would:

- add a table or column that stores **derivable** state, or add any **container/group** entity;
- **mutate or delete** from the append-only log, or make `ConceptState` non-derivable;
- change the **mode Protocol**, or special-case a mode in the engine;
- add a **second LLM call site** or bypass the router;
- introduce **roles / permissions / moderation**, or a forced merge in the proximity check;
- change **attribution granularity** (topic → per-concept) or the recognition model;
- touch the **emergent-set / proximity / governance** model, or the offline event-sourcing model;
- make a **cross-feature data-model** decision (what "connection" spans, the `SubjectFamily` set,
  what counts as a session);
- trade **offline-safety** (append-only, derivability) for local convenience.

**Everything smaller — decide and build:** endpoint shapes, internal module structure, test layout,
prompt wording, which specific fast model, error-message copy, cache keys, worker plumbing. Don't
escalate those; just follow §1 and ship with tests.
