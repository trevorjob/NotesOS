# NotesOS v2 — Page Map (design brief)

> **What this is.** The screen-by-screen inventory of the native client — the *functional
> contract* Claude design turns into direction. It is the by-screen slice of
> [`system-spec.md`](./system-spec.md) (behaviour by feature) and
> [`v2-redesign-plan.md`](./v2-redesign-plan.md) Phase C (backend status per surface).
>
> **The seam (read this).** This doc says *what each screen is for, what backs it, what states it
> has, and the constraints it must respect.* It deliberately does **not** prescribe layout,
> hierarchy, or visual treatment — that's design's judgment. Where it names a shape
> it's describing *function*, not a wireframe. Same discipline as our prompt work: an
> objective + constraints, never a template. If a constraint here forces an ugly screen, that's a
> flag to come back to the architect, not a spec to grit through.
>
> **How to read an entry.** *Purpose* (one line) · *Backed by* (endpoints/services + build status) ·
> *Holds / states* · *Must respect* (non-negotiables). Backend status tags: ✅ done · 🔧 small seam ·
> 🚧 gap to build · ⚠️ escalation.
>
> **The terse index:** [`page-spec.md`](./page-spec.md) is the one-line-per-page inventory (function
> only) built by walking a full user journey — use it to confirm no page is missing; this doc is the
> fuller per-screen contract.

## Global constraints (apply to every screen)

These come from the locked design + the build invariants. Design must honour them everywhere:

- **Brand:** creative, playful, bright; *notebook* aesthetic (warm cream, grain, amber highlighter,
  hand-drawn accents). Full detail in `CLAUDE.md` Design Context + `.impeccable.md`. Texture before
  flatness; playful restraint; study-forward. Both light (warm paper) and dark (night journal).
- **No streaks. No leaderboards. No vanity numbers.** Progress is honest, personal, continuous.
- **Warmth, never anxiety.** Lead with growth, whisper the fading. No guilt, no dark patterns.
- **Offer, never force.** Every proximity/merge/discovery surface ends in an *offer*; "make my own"
  always stays live.
- **Notes are structure-first and always math-capable.** A note is a *studiable structure*, not a
  prose wall or a comprehensive dump; it renders math/worked-examples/itemised structure where the
  material calls for it, prose only where an idea needs flow. Every note surface can render math.
- **Accessibility WCAG AA.** Grain never impedes legibility; illustrations `aria-hidden`; respect
  `prefers-reduced-motion`; the Caveat handwriting font is labels/annotations only, never body.
- **Phone-first identity.** Phone (OTP) is the primary login; email/Google secondary.

---

## Navigation model — focus by default, everything one gesture away

> The single biggest v0 usability failure was **drill-down switching**: changing topic or course
> meant climbing out of where you were (topic → course → course list → other course → its topics),
> a click per level. v2 eradicates this. The fix separates two jobs that v0 conflated:

- **What you land on is focused.** The home is a *doorway* (C1) — the server picks the one
  highest-value next action and the app opens on it, not on a menu. This kills "what should I
  study?" paralysis. **Do not turn the doorway into a dashboard to solve navigation** — that's the
  wrong lever, and it fights the product's own thesis.
- **How you move is flat and universal.** From *any* screen, **one gesture** opens a **fast
  switcher** that jumps **directly** to any course, topic, or note — recents first, search for the
  long tail. You never climb the tree to cross it. This is an *invoked* affordance (a quick-switch /
  spotlight), **not** a persistent tab bar or always-drawn nav chrome.

Principles design must honour:

- **Flat, not hierarchical.** Every destination (course, topic, note, progress) is directly
  addressable. Crossing from one topic to another is one jump, never an ascent-then-descent.
- **Recents-first, zero-typing for the common case.** The things you touch most — the current
  course's other topics, recent notes, what's due — sit at the top of the switcher with no query.
  Search is the long tail, not the default path.
- **Context carries.** Switching topic within a course keeps you in the study frame; it doesn't
  dump you back to a list. Movement is lateral, not "back out and re-enter."
- **The study loop barely navigates.** Launching retrieval from inside the note (the signature) and
  the home doorway mean the highest-frequency actions never route through a menu at all. Navigation
  is for the *exceptions* — going somewhere the app didn't already put in front of you.
- **≤1 gesture to anywhere; never a dead end.** Every screen keeps the switcher reachable, so
  "stuck three levels deep" is structurally impossible.

**Two study front doors (don't merge them).** Studying has two intents, and they want different
entries — this is *not* a contradiction of "focus by default":

- **Review — zero-config doorway (C1).** The app decides ("3 fading in Thermo, 5 min") and opens on
  it. Reactive to your FSRS schedule; the daily loop; **no setup, ever.**
- **Practice test — deliberate builder (C9).** *You* decide: pick a course or topics → count → type →
  generate a graded, shareable test. Proactive, exam-shaped, occasional. **Config is right here** —
  it's a deliberate act, not a nudge, so it doesn't violate the doorway thesis (the doorway removes
  the *daily* "what do I study"; the builder serves the *occasional* "I'm cramming for Friday").

Both feed one mastery map — a practice test records per-concept attempts just like review, so
cramming re-lights the note and the review loop learns from it.

*This resolves the design-system §6/§10 open question ("whether a persistent global nav exists at
all"): a persistent global **tab bar / dashboard — no**; a persistent, one-gesture, **flat access
affordance — yes**. The switcher is invoked, not always-drawn, so it coexists with the doorway
instead of competing with it. The "quiet secondary access to courses/progress" the Home entry names
is this switcher; the Course list / Topic view screens are its destinations, not the only path in.*

---

## 1 · Auth & onboarding

- **Login** — *Purpose:* get a returning user in, phone-first.
  *Backed by:* ✅ `POST /api/auth/login`, OTP verify (WhatsApp), refresh; Google OAuth secondary.
  *Holds / states:* phone entry → OTP sent → code entry → success/fail; resend/cooldown; Google path.
  *Must respect:* phone is primary; OTP errors are gentle and specific; never leak whether a number
  is registered.
- **Register / sign-up** — *Purpose:* create an account and place the user on the spine.
  *Backed by:* ✅ `POST /api/auth/register`; school typeahead `GET /api/schools/search`; optional
  `program`, `entry_year`.
  *Holds / states:* phone + OTP; school pick (curated list *or* type-your-own, canonicalised in);
  optional signals; validation states.
  *Must respect:* school is a typeahead over a curated list with free-type fallback — not a plain
  text box; every optional field is genuinely optional (no forced funnel).
- **OTP verify** — *Purpose:* confirm the phone. Often a step inside login/register rather than a
  page; design decides. *Backed by:* ✅ OTP endpoints. *Must respect:* resend cooldown, expiry,
  clear failure copy.
- **Onboarding (C7)** — *Purpose:* first-run — open on a *gap-first pretest*, not a tour; show value
  while first content processes.
  *Backed by:* ✅ composition over pretest mode + `/api/retrieval/next-action` + capture; no new
  server work.
  *Holds / states:* welcome → capture-or-sample → **demo-while-processing** (something useful to do
  while synthesis runs) → first pretest → first result.
  *Must respect:* value before setup; the "synthesizing" wait is *filled*, never a spinner; tone is
  the encouraging study-partner voice.

---

## 2 · Core study loop (the heart — design this first)

- **Home / entry thing entry (C1)** — *Purpose:* a doorway, not a dashboard. Land the user on the single
  highest-value next action (usually review what's fading).
  *Backed by:* ✅ `GET /api/retrieval/next-action` (B3) returns the one thing
  (kind/mode/scope/reason/estimate).
  *Holds / states:* the hero thing (+ reason + time estimate); quiet secondary access to
  courses/progress; empty state (nothing due yet — no content); returning-with-fading state.
  *Must respect:* **one thing leads** — don't rebuild a mode-picker grid; the server already chose.
  The reason ("3 concepts slipping in Thermodynamics") is shown, gently.
- **Note canvas — active surface (C2)** — *Purpose:* the wedge. The consolidated, studiable note a
  student reads *instead of* their scattered materials, wired to push into retrieval.
  *Backed by:* 🔧 note = `TopicKnowledge` (structure-first synthesis, B10/B12 shipped); mastery =
  `Concept`/`ConceptState`; ⚠️ **span-linking note↔concept and claim-level "says who?" is an
  escalation** (attribution is topic-level today — build-guide §5 / plan C2); source-read view 🚧 owed.
  *Holds / states:* the note body (prose + math + itemised structure, per material); terms **lit by
  mastery** (solid glow / fading dim — the note-as-live-map / anti-fluency mechanic); tap a
  concept/paragraph → **launch a retrieval right there**; **"says who?"** provenance on demand;
  **"read the original"** → the raw source layer; incremental states — *empty · synthesizing (writes
  itself) · ready · updated ("what changed since you last read" · "Ada added this")*.
  *Must respect:* structure-first + always-math-capable (globals); **the mastery heat-map is the
  design, not optional** (exact visual treatment is design's call); trust reads as *one voice* — no
  "Source A vs B" inline, only the quiet "says who?" + "your cohort built this"; the raw source stays
  reachable so the note itself can be lean.
- **Source reader ("read the original")** — *Purpose:* the raw uploaded material behind the note —
  the verbatim source layer that lets the note go lean (B12's two-layer model).
  *Backed by:* 🔧 the data exists (`Resource` + transcriptions/chunks); a readable view over it is a
  small read seam (B12 names it as owed).
  *Holds / states:* the original transcription/text per resource, readable; which resources back this
  topic; empty (no sources); quarantined items uploader-only.
  *Must respect:* read-only; reachable from the note's "read the original"; offline-readable (§7); it's
  the archive, not a second note — no synthesis, just the verbatim.
- **AI tutor chat** — *Purpose:* ask anything about the topic/course in your own words; answers
  grounded in your own materials.
  *Backed by:* ✅ `study_agent` + `POST /api/study/ask` (+ `/stream` SSE, A1); RAG over chunks
  (`rag.py`), subject-aware (B10).
  *Holds / states:* a conversation (question → grounded answer, streams in); topic-scoped *or*
  course-wide; empty (no question yet); thinking/streaming; error.
  *Must respect:* answers are grounded in the user's materials, not open-web; math renders as math
  (B10); the persona knobs (tone/emoji/style) apply and are *orthogonal* to subject shape; course-wide
  chat stays neutral, a topic chat is subject-aware.
- **Listen — audio lessons** — *Purpose:* hands-free study — play the topic's short audio lessons.
  *Backed by:* 🔧 `audio_generator` + `audio_worker` produce **N rotating TTS variants** per topic
  (generation done; verify the list/fetch/serve endpoint + stored audio URL).
  *Holds / states:* a player (play / pause / scrub); the set of *rotating* variants (not one repeated
  lesson); generating (not ready yet); ready; downloaded/offline; error.
  *Must respect:* multiple distinct takes, never one lesson on repeat (anti-sameness, B13); downloaded
  audio plays offline (§7); background / lock-screen playback.
- **Retrieval session run** — *Purpose:* the actual practice — where a concept gets tested and
  scheduled. (First-class screen; not explicitly in C1–C8.)
  *Backed by:* ✅ `POST /api/retrieval/next` (generate) → `POST /api/retrieval/attempt`; ✅
  `POST /api/retrieval/reveal` (B9, STEM self-calibration); ✅ `POST /api/retrieval/{dump,recap}/next`
  + `/attempt` (free-recall set modes); ✅ `GET /api/retrieval/modes`; ✅ photo answers (B8, paper →
  vision transcribe → confirm → attempt).
  *Holds / states:* **one run surface, parameterised by mode** — the modes differ in *stimulus shape,
  input, and how the result reads*, not in a screen each. The base flow is *generate →
  (predict confidence) → respond → outcome + updated state + calibration (quietly)*. The six modes and
  the two overlays are broken out below.
  *Must respect:* **predicted-confidence is captured BEFORE the answer/reveal** (the calibration
  guarantee — ordering is load-bearing); math renders as math; self-grade vocabulary is the closed
  set (again/hard/good/easy); a miss is never punished — it's just scheduling. **Don't build a
  mode per screen** — build one surface that flexes.

  **The modes** *(grounded in `services/retrieval/*_mode.py` + `dump.py`/`recap.py`)* — two shapes:
  a **posed question** (quiz, pretest) or an **open prompt you produce against** (ramble, teach,
  dump, recap):
  - **Quiz** — a posed question on **one** concept. Either **MCQ** (tap one of four; instant, binary
    — a right answer is "good", never "easy", so a lucky guess can't graduate the concept) or
    **short-answer** (type/speak; AI-graded on key points → feedback + what you missed). The everyday
    review beat.
  - **Pretest** — the *same* question shape, but posed **before** you've studied; framed gently ("a
    guess is fine"). A correct pre-study answer is capped so it never flings the concept far into the
    future — its real job is priming encoding and feeding calibration. Design the *framing* difference,
    not a different screen.
  - **Ramble (brain-dump, single concept)** — one open prompt: *"tell me everything you understand
    about X."* You talk or type freely; judged on **how much of the concept you surfaced** and what
    you missed — no cue to lean on, so producing the structure is the work. Voice-natural; long-form
    input.
  - **Teach** — *"explain X as if teaching a classmate who's never seen it."* Judged on
    **correctness · completeness · clarity** + what a learner would still be confused about (a wrong
    explanation can't be rescued by fluency). A strong explanation is also raw material for a note
    *contribution* later — surface that quietly, never as pressure.
  - **Brain dump (whole topic)** — one uncued prompt for the **entire topic** at once; your single
    monologue is graded against the topic's **full concept set → one result per concept** (a concept
    you never mention reads as a genuine miss, not a zero to grade around). The widest net; distinct
    flow (`/dump/next` → `/dump/attempt`) that returns a *per-concept breakdown*, not one score.
  - **Recap** — the same set-shaped free recall, scoped to **the last session's concepts** ("did last
    session stick?"). Same per-concept result shape as dump; a concept you don't surface is a real
    lapse. Distinct flow (`/recap/next` → `/recap/attempt`).

  **Two overlays that ride on top** (not modes of their own):
  - **STEM self-calibration (B9)** — on STEM topics, quiz/pretest can pose a **worked problem**: you
    **solve on paper → predict confidence → reveal the worked solution → self-grade** (again/hard/
    good/easy). The reveal beat is unique to this path and the ordering is the whole calibration
    guarantee (confidence is stamped in *at reveal*, before you see the solution). A **numeric** STEM
    problem skips the reveal — one right number, checked server-side within tolerance. This is the
    only self-graded and the only reveal-carrying flow.
  - **Photo answers (B8)** — any typed answer can instead be a **photo of paper work** →
    transcribed → **you confirm/correct the transcription** → submitted through the normal attempt
    flow. Photos are ephemeral (never stored); only the text you confirm is ever graded. Applies to
    quiz short-answer, ramble/teach, and dump/recap alike.

  **What varies screen-to-screen (the design axes):** *stimulus* (posed question vs open prompt) ·
  *input* (tap · type/speak · photo-of-paper) · *grading* (instant/binary · AI coverage-and-gaps ·
  self-graded · server-checked number) · *result granularity* (one concept vs a per-concept set) ·
  *the confidence beat* (optional in general — see design-system §7 — but a **mandatory ordered step**
  for STEM worked problems).
- **Test builder — authored practice test (C9)** — *Purpose:* the **deliberate** study door (the
  other front door — see *Navigation model*): "I'm prepping for an exam — make me a graded test on
  these topics." Distinct from the C1 doorway (which *removes* choice); here choosing is the point.
  *Backed by:* 🚧 B14 (authored test on the retrieval atom — new). Selection over course/multi-topic;
  generated async with progress; persisted + course-shared; taking it records per-concept attempts.
  *Holds / states:* pick scope (a course **or** multi-select topics) → count (1 / 5 / 10 / …) → type
  (mcq · short-answer · essay) → **generating (per-question progress, not a spinner)** → ready →
  **take it** (reuses the *Retrieval session run* surface) → derived summary ("8/10 — what firmed up /
  what's still fading"). Also: a **shared list** — tests classmates authored for this course.
  *Must respect:* **config is right here** (deliberate act, not a nudge — the one place setup belongs);
  **quiz + pretest only** (ramble/teach/brain-dump don't set-ify); a generated test is **communal**
  ("Ada made a 20-q mock on Unit 3") — appears for the whole course, no leaderboard on scores
  (invariant); **taking it feeds the mastery map** (the summary is derived from per-concept attempts,
  never a stored score); the *runner* is the existing run surface — don't design a second one.
- **Progress — spatial (C3)** — *Purpose:* see your living knowledge state.
  *Backed by:* 🚧 per-concept topic-scoped mastery read endpoint to build (data all exists —
  `ConceptState` + concepts-by-topic; calibration from the attempt log); pure read, no schema change.
  *Holds / states:* **the note lit by mastery IS the progress map** (reuses the note↔concept linking)
  — solid glow / fading dim across your own notebook; a dedicated stats view is *optional depth*;
  calibration surfaced "when relevant, not in your face"; empty state (no history yet).
  *Must respect:* spatial not scoreboard; lead-with-growth/whisper-the-fading; no streaks/leaderboards;
  calibration is the signature-but-quiet metric.
- **Capture dump (C4)** — *Purpose:* frictionless in — drag/snap/record raw material, confirm the
  proposed structure.
  *Backed by:* 🔧 `api/capture.py` (A2) — *verify its propose→confirm contract matches this UX* (a
  dump returns an amendable **proposal**, never an auto-commit).
  *Holds / states:* input (files / photo / audio / text) → processing → **proposed topic structure**
  (ordered, amendable) → confirm; per-item progress; partial/failed-item states.
  *Must respect:* the user amends before commit — the proposal is an offer; nothing is filed silently.

---

## 3 · Spine & social

- **Course list** — *Purpose:* the user's courses, filed under terms. *Backed by:* ✅ courses API +
  `term_id` filing. *Holds:* courses grouped by term; per-course activity; add/join entry points;
  empty state. *Must respect:* Term is a *label/filing*, not a container — no "class group" object.
- **Topic view** — *Purpose:* inside a course — its topics and resources; the jump-off to notes.
  *Backed by:* ✅ `/api/{course_id}/topics`, resources API. *Holds:* topic list, per-topic
  note/knowledge status, resources, upload entry; live "active users" presence (`WS /ws/{course_id}`).
  *Must respect:* switching to another topic (or another course's topic) is a **lateral jump via the
  switcher**, not a climb back up to a course list — this screen is a destination, not a required
  waypoint (see *Navigation model*).
- **Course create + proximity offer** — *Purpose:* create a course, but first offer the near-match.
  *Backed by:* ✅ `POST /api/courses` returns `{proximity_check, matches[]}` (200, creates nothing);
  re-POST `force=true` to fork; join via `POST /api/courses/join`.
  *Holds / states:* create form → **"did you mean this?" offer** (each match shows *member_count* +
  *why* it's offered) → join *or* make-my-own. *Must respect:* **offer never forces**; "make my own"
  is always present and equal.
- **Join by invite** — *Purpose:* enter a course by code. *Backed by:* ✅ `POST /api/courses/join`.
  *Must respect:* every course is invite-reachable; no public/private concept.
- **Discovery** — *Purpose:* find your people and their courses via the emergent graph.
  *Backed by:* ✅ `GET /api/discovery/classmates`, `GET /api/discovery/courses` (pure reads).
  *Holds:* classmates (shared-course count); "courses your classmates take" you're not in; empty
  states. *Must respect:* discovery *surfaces*, it never enrolls — `join` is the only join primitive;
  an activity gate hides empty solo courses.
- **Term filing** — *Purpose:* create/manage personal terms and file courses. *Backed by:* ✅
  `/api/terms` (vocab/list/create/update/delete), `PATCH /api/courses/{id}/term`. *Holds:* term
  composer (controlled components → one canonical label); assign course → term.

---

## 4 · Voice (C6 — ships dark)

- **Voice conversational UI** — *Purpose:* co-present, active-listening study by voice.
  *Backed by:* ✅ `WS /ws/voice/{course_id}` (B5); frame vocabulary in `services/voice/protocol.py`.
  Client owns STT, VAD endpointing (`speech_final`), barge-in, playback, mic-permission states.
  *Holds / states:* listening / thinking / speaking; barge-in; permission + error states.
  *Must respect:* **lane ships dark behind `ENABLE_VOICE_LANE=false`** — design it, but it's not in
  the launch-critical path; subject-shape (STEM works the example) carries here too.

---

## 5 · Account & system

- **Settings** — *Purpose:* personality + account. *Backed by:* ✅ personality endpoints (tone /
  emoji / explanation-style *persona* knobs); ✅ `DELETE /api/auth/me` (D3, re-auth-confirmed
  account deletion). *Holds:* persona controls, profile (school/program/year/phone), sign-out,
  **delete account**. *Must respect:* persona axis is *separate* from subject-shape; deletion is the
  one sanctioned destructive action (de-identifies attempts, keeps the shared substrate).
- **Notifications / decay nudge** — *Purpose:* the warm pull back — what's fading, what a classmate
  added, recognition. *Backed by:* ✅ `/api/notifications`; the decay engine + recognition (behind
  `ENABLE_RECOGNITION`). *Holds:* decay nudges ("time to revisit"), "Ada added this", "N built this
  note", digest. *Must respect:* gentle, growth-led; recognition is warm and *un-ranked*.
- **Contribution visibility (C8)** — *Purpose:* "N built this note" — communal warmth, no scoreboard.
  *Backed by:* 🔧 small aggregate read endpoint over the B1 substrate. *Must respect:* **aggregate
  only, never ranked** (no-leaderboard is an invariant).
- **Report / block (D5)** — *Purpose:* the minimum honest UGC safety surface.
  *Backed by:* 🚧 `POST /api/reports` (D5) → reuse quarantine machinery → owner review.
  *Holds:* report a resource/note/AI output; block a user. *Must respect:* no moderation theatre —
  the reporter doesn't see an outcome loop; block hides a user's *future* content from the blocker.

---

## 6 · Cross-cutting states (system-spec §12 — a designer cheat-sheet, not screens)

Every relevant screen must define these; they're where the product feels alive or broken:

- **Empty** — scaffold exists, no content yet (course, topic, note, progress). Hand-drawn empty
  states, encouraging copy — never a dead end.
- **Loading vs. synthesizing** — a spinner is loading; **synthesis visibly *writes itself*** (the
  note streams into place). These read differently.
- **Updated** — "what changed since you last read"; "Ada added this section" (recognition, on the note).
- **Offline / sync (C5)** — *Backed by:* ✅ `/api/sync/*` (B6). Cache-first; the client owns the local
  store, a 10–15 min poll, and a replay queue (`client_event_id` per attempt; only quiz/pretest push).
  Design the offline boundary + a quiet sync indicator; never block study on the network.
- **Quarantine / held** — content held out of the shared surface (merge gate or a report) is
  *uploader-only*, shown plainly, no shaming.
- **Error** — specific, kind, recoverable; never leaks internals.

---

## Open items design should know are *not* settled

- **C2 "says who?" claim-level attribution** — ⚠️ architect escalation (attribution is topic-level
  today). Design the affordance; the *grain* it can show is pending the synthesis output contract.
- **Figures / diagrams in notes (B11)** — capture is text-only today, so inline figures are a tracked
  deferral. **Design the note to *hold* an inline figure anyway** (leave the slot) so it's not a
  retrofit when backend delivery lands.
- **Deferred, don't design yet:** in-flight quiz coalescing, model tiering — no UI implications.
