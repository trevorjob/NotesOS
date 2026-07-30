# Listen — audio artifacts, personalization & the credits seam — plan

> **Status: design, not built (2026-07-30).** Escalate-first artifact for generalizing the
> audio-lesson system. Read before writing code; react before we build. Canonical
> architecture ([`v2 redesign plan`](../docs/v2-redesign-plan.md))
> wins on conflict; this extends the audio surface, it doesn't change the retrieval engine,
> grading, or the FSRS invariant.
>
> Raised by the user 2026-07-30: current per-topic explainer audio is fine, but Listen should
> grow **context-level, user-requested audio** on top of it, with proactive weak-spot
> breakdowns, a calc-heavy modality gate, and a monetization path (free at launch → credits).

---

## 1. The reframe — one artifact, three axes

`AudioLesson` today is hardwired to **one** shape: topic-scoped, global, default-lens, one
voice. The requested variations are not separate features — they are the same object with three
knobs:

| Axis | Values | Today | Unlocks |
|---|---|---|---|
| **Scope** — what it covers | `course` · `topic` · `concept` · `concept_cluster` | topic only | concept-level "explain just this" |
| **Lens** — how it's told | `default` · `user_instruction` · `remediation` · `exam_focused` · `slower` · `worked_example` | default only | user requests, weak-spot breakdowns |
| **Owner** — who it's for | `global` (shared, free) · `personal` (user-owned, credited) | global only | "request your own" |

Every requested behaviour collapses into a preset over these axes:

- **Today's general audio** = `(topic, default, global)` — free, shared, deduped across all users.
- **"Explain this concept my way"** = `(concept, user_instruction, personal)` + `instruction`.
- **Detected-weakness breakdown** = `(concept, remediation, personal)` — auto-suggested.
- **The mock's "Takes"** (overview / exam / slower) = lens presets, not fabricated data. This
  reconciles [`listen.tsx`](../mobile/src/app/listen.tsx) with backend reality instead of cutting it.

**One generation path, one worker, one dedup rule:** `global + same scope + same lens` → reuse
the existing artifact; `personal` → always fresh, with the user's own context baked into the prompt.

## 2. The data model — `AudioArtifact` (new)

Decided 2026-07-30: **new model**, not an in-place extension of `AudioLesson`. Existing lessons
backfill in as `(topic, default, global)`; `AudioLesson` is retired after backfill.

```
AudioArtifact
  id
  scope_type      enum(course|topic|concept|concept_cluster)
  scope_ref       UUID            # topic_id / concept_id / cluster key
  knowledge_id    UUID nullable   # source note version, for staleness
  lens            enum(default|user_instruction|remediation|exam_focused|slower|worked_example)
  instruction     text nullable   # only for user_instruction
  owner_id        UUID nullable   # null = global/shared; set = personal
  cost_credits    int default 0   # truth for the ledger even while all-zero (§5)
  voice           str
  script          text nullable
  audio_url       text nullable
  duration_seconds int nullable
  status          KnowledgeStatus
  error_message   text nullable
  stale           bool default false   # flipped when source knowledge re-synthesizes
  generated_at / created_at / updated_at
```

Dedup / lookup keys:
- `(scope_type, scope_ref, lens)` **where `owner_id is null`** — unique-ish, the shared artifact.
- `(owner_id, scope_type, scope_ref, lens, instruction_hash)` — a personal artifact's identity.

Model change + migration (autogenerate) is architecture-worthy; this doc is the escalate.

## 3. Generation path (unchanged shape, generalized inputs)

`audio_generator` already splits cleanly into `generate_script(knowledge, name)` →
`generate_audio(script, voice)`. Generalize the script step to take **`(scope, lens, instruction,
user_context)`** instead of just a topic note:

- **Scope** decides the source text: topic note (as today), a single concept's statement +
  its slice of the note, or a cluster.
- **Lens** selects the prompt strategy (principle-guided, per the prompt-design invariant —
  not templates). `worked_example` narrates the steps of a solved problem; `remediation` leads
  with the misconception.
- **`user_context`** (personal only) = the user's real `RetrievalAttempt` answers for the
  concept, so remediation is *"you keep saying X — here's why it's actually Y,"* not a generic
  re-explain.

`audio_worker` stays the single worker; job payload carries `artifact_id`. Global generation is
enqueued by `knowledge_worker` as today; personal generation is enqueued by the request endpoint (§4).

## 4. Endpoints

- `GET  /audio/{scope_type}/{scope_ref}` — latest ready artifact for a scope + lens (query
  `?lens=`, `?owner=me|global`). Replaces `GET /topics/{id}/audio`; keeps the passive-consume signal.
- `POST /audio/request` — body `{scope_type, scope_ref, lens, instruction?}`. Runs the credits
  gate (§5), dedups, enqueues, returns `202` + artifact id. This is "request your own."
- `POST /audio/{id}/regenerate` — as today, gated the same way.
- Suggestions surface via the existing retrieval/home feed, not a new endpoint (§6).

## 5. The credits seam — design now, build never (yet)

YAGNI on billing. Put the **chokepoint** in from day one so it's never retrofitted:

```
can_generate(user, artifact) -> Decision(allow: bool, cost: int, reason)
```

- Launch: returns `allow=True, cost=0` for everything.
- Invariant that never changes: **global/default artifacts are always free** (one generation
  serves everyone — a shared good); **personal artifacts always route through the gate** (cost 0 today).
- `cost_credits` is written on every artifact from the start, so the ledger has truth while it's all zeros.
- Later, `can_generate` becomes credits / pay-as-you-go with **zero call-site changes**.

## 6. Remediation auto-suggest — the differentiator, nearly free

The "detect where they're lacking" signal already lives in `ConceptState`: `lapses`, `reps`,
`difficulty`, `stability`, `last_grade`, `due`. A weak-concept query (high lapses / low stability /
repeatedly `again`) is the trigger — no new detection to build.

Flow: a lightweight selector ranks a user's weakest concepts → surfaces a suggestion in the
retrieval/home surface (*"You keep missing X — want a 4-min breakdown?"*) → tapping fires
`POST /audio/request (concept, remediation, personal)`. The generation prompt pulls the user's
actual wrong answers as context. This is the personalized-tutor moment and the natural first
thing to charge a credit for.

## 7. Calc-heavy — a modality gate in the one right place

`subject_profiles.py` is *"the one place a subject family becomes retrieval behaviour."* Add a
**modality dimension** to `SubjectProfile`: `audio_suitability` (0..1), later `video_suitability`.

- STEM / calculation-heavy → low audio suitability → UI does **not** offer a plain explainer;
  it offers the `worked_example` lens (narrating a solved problem *does* work in audio) or says
  "better read" and defers to the future video lane.
- Prevents spending compute/credits on useless audio. One-entry-per-family change — the
  abstraction's intended shape. Video is out of scope here; the gate just leaves room for it.

## 8. Additions (cheap, high perceived value)

- **Follow-up loop** — after listening, "ask about this" hands to the existing voice lane, or
  spins a short personal addendum artifact.
- **Commute playlist** — course-scoped queue of topic artifacts; pure client-side sequencing.
- **Freshness** — mark artifacts `stale` on `knowledge_id` change; lazily regenerate on next request.
- **"Answer out loud" pauses** — the script pattern already has concept→question→pause→answer;
  the honest, cheap version of the mock's "active-listen" without pulling in the full voice lane.

## 9. Phasing (all four slices in scope)

- **Phase 0 — foundation + real player. SHIPPED 2026-07-30.** `AudioArtifact` model +
  backfill migration; generalized generator/worker/endpoints; real expo-audio playback in
  [`listen.tsx`](../mobile/src/app/listen.tsx). Replaced the static mock.
- **Phase 1 — personal + lens requests. SHIPPED 2026-07-30.** `POST /audio/request` (scope +
  lens + optional instruction, always-fresh, never deduped); the credits **seam** in
  `app/services/audio_credits.py` (free/allow today, zero call-site changes later); lens
  directives added to the script prompt (exam_focused/slower/worked_example/user_instruction,
  additive — default lens byte-identical to Phase 0); concept-scope generation (a single
  concept + its topic's note as context); real lens picker on `listen.tsx` (the actual
  "Takes" — Overview free/global, the rest personal/"just for you"); "Explain this my way" on
  the note's concept sheet → free-text instruction → concept-scoped personal audio. Fixed a
  latent bug in the same pass: `upload_audio`'s Cloudinary `public_id` was keyed by
  `topic_id` alone, which would have made concurrent personal artifacts for the same topic
  overwrite each other's file — now keyed by `artifact_id`.
- **Phase 2 — remediation auto-suggest. SHIPPED 2026-07-30.** `weakest_concepts()` reuses the
  note's own "shaky" heat-map label (`derive_mastery`) over `ConceptState` — no new detection.
  `recent_wrong_answers()` reads the caller's actual missed `RetrievalAttempt` rows
  (question + their answer) as generation context. `GET /topics/{id}/weak-concepts` is the
  surface-agnostic suggestion source; `POST /audio/request` now accepts `lens=remediation`
  (concept-scope only — 400 for topic scope, since remediation is inherently about one
  concept). Suggestion surface (§10) decided: **both** the note screen and Listen (not yet
  the ambient/home feed — deferred), via a shared `WeakConceptSuggestion` component that
  routes to `listen.tsx` in concept+remediation mode.
- **Phase 3 — calc-heavy modality gate. SHIPPED 2026-07-30.** `audio_suitability` (0..1) added
  to `SubjectProfile`, with `is_audio_suitable()` as the one threshold check (STEM=0.3, below
  threshold; everything else ≥0.9). The gate only withholds the "generic explainer" lenses —
  `default`/`exam_focused`/`slower`, which are all just angles on the same narrated note — for
  unsuitable scopes; `worked_example` (narrates solved-problem steps) and the personal
  `user_instruction`/`remediation` lenses are never gated, since the caller explicitly asked for
  those and Phase 2's remediation breakdowns matter most for exactly the STEM concepts students
  struggle with. Enforced in three places: `POST /audio/{scope}/regenerate` and `POST
  /audio/request` reject with 422 up front; `audio_worker._create_global_default` is the
  worker-side backstop that silently skips auto-generating a global default for an unsuitable
  topic (covers the automatic post-synthesis trigger, which has no API caller to 422). `GET
  /audio/{scope_type}/{scope_ref}` now also returns `audio_suitable` on every response (real or
  pending-stub) so `listen.tsx` can steer off a hidden lens before the user ever hits a 422 —
  and hides the Overview/Exam-focused/Slower chips in favour of Worked example, with a one-line
  explanation, when the topic isn't suitable.
  - **Fixed in the same pass** (a pre-existing gap surfaced while wiring concept-scope family
    resolution, not new Phase 3 scope): `GET /audio/{scope_type}/{scope_ref}` previously 400'd on
    any `owner=me` request and never checked enrollment or existence for `scope_type=concept` —
    meaning concept-mode Listen (Phase 1/2's personal/remediation requests) could never actually
    poll or display its own result, and concept-scope reads had no authorization check at all.
    Both are now fixed: `owner=me` returns the caller's own latest artifact for a scope+lens, and
    concept scope resolves the concept, 404s if missing, and enrollment-checks via its course.

## 10. Decisions & open questions

**Decided 2026-07-30:**

- **Scope enum ships complete** — `course|topic|concept|concept_cluster` all land in the first
  migration, even though `course` / `concept_cluster` have no consumer until later phases. Avoids
  a second enum migration; the unused values are inert until a scope path uses them.
- **Personal artifacts are kept indefinitely** for now. No eviction / TTL logic. Revisit when
  storage cost or the credits ledger makes retention matter — it's an additive change, not a rework.
- **No voice selection.** One fixed voice per lens (not user-configurable), same as today's
  hardcoded default. `AudioArtifact.voice` stays a plain column for future flexibility, but no
  UI or endpoint exposes it. Revisit only if users ask.
- **Suggestion surface: note screen + Listen, not the ambient/home feed (yet).** The retrieval-
  experience feed from [`retrieval-experience.md`](./retrieval-experience.md) isn't built yet —
  adding the suggestion there now would mean building part of that direction early, scoped
  narrowly. Both existing surfaces got it instead via one shared `WeakConceptSuggestion`
  component; the ambient feed is explicit future work, not dropped.

**Still open, genuinely undecided — do not build against a guess:** none currently — revisit
as Phase 3 raises new ones.
