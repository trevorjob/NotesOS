# Retrieval as a first-class surface — experience & flow design

> **Status: design draft, for discussion. Not yet built (beyond the wiring noted in §8).**
> Raised by the user 2026-07-30 — this reopens the §1 "retrieval-mode picker" complaint
> that was parked in [`mobile-integration-plan.md`](./mobile-integration-plan.md). Argue it
> on paper here before touching layout. Canonical behaviour is
> [`system-spec.md`](./system-spec.md) §5 (the retrieval engine) and §8 (the habit loop);
> this doc is *how the experience is shaped*, not new engine behaviour.

---

## 1. The problem

Retrieval today is reached as **a list of options** — a bottom-right button opens a sheet of
6 modes, you pick one, you land on a screen where you can "change mode." That framing is
backwards. The user's words:

> *"the reason i built the backend this way is because the expectation is that retrieval
> basically lives and is a part of the app — not just a bunch of options. You should still be
> able to select the one you want to do, sure, but with a much better experience and
> interface."*

A flat mode-list treats every mode as an equal, context-free choice and makes the *user* do
the work of deciding what to study and how. But the engine already knows both. A menu hides
that.

## 2. The principle (DECIDED 2026-07-30)

**The engine chooses by default; you override deliberately.** Two layers, never one menu:

1. **Fast path (ambient, engine-driven).** Retrieval appears *where the content is*, with the
   mode already implied by context. One tap starts the right thing. This is the default and
   the common case.
2. **Deliberate path (pick, as the expand).** You can still choose a specific mode — but it's
   the *expansion* of the fast path, not the front door, and it's presented **context-worthy**
   (only modes that fit the current scope, ordered by subject affinity), never as a flat list.

Everything below follows from this.

## 3. Where retrieval lives across the app (the surface map)

Retrieval isn't one screen; it's a capability surfaced at the point of relevance. Each surface
already has the backend to drive it.

| Surface | Trigger | Mode (engine-implied) | Backend |
| --- | --- | --- | --- |
| **Home hero** | Land on home | `GET /next-action` picks kind+mode+topic | ✅ wired §8 |
| **Note — tap a concept** | Tap a lit term | concept-scoped; state implies mode (shaky→quiz, section→ramble) | ✅ `/next` per-concept |
| **Note — finished reading** | Reach end of a just-read topic | **dump** (read→dump beat, B7) | ✅ `next-action` returns `kind:"dump"` |
| **Course / topic page** | Open a course | `GET /next-action?course_id=` — "the thing to do in *this* course" | ✅ scoped next-action |
| **FAB (global)** | Tap anywhere | default = `next-action`; expand = pick | ⬜ needs the FAB rework |
| **Session close** | Finish a bout | warm close + "recap tomorrow?" hook | ⬜ needs session flow |

The through-line: **the user never has to know the mode taxonomy to study well.** Power users
who *want* a specific mode always can (the expand), but it's an affordance, not a toll gate.

## 4. The FAB — a "study now" doorway, not a mode menu

- **Draggable / movable** (user asked). Persist its position locally; it should never cover
  content it's near.
- **Default tap = study now** → `GET /next-action` (optionally scoped to the screen's course/
  topic when on one). The engine picks; the user just goes. This is the fast path.
- **Expand = pick (DECIDED 2026-07-30): long-press, *plus* a visible affordance so it's
  discoverable.** Long-press is the fast, "cool" gesture for power users — but a hidden gesture
  no one finds is a dead feature, so it's backed by two aids: (a) a **small persistent caret /
  stacked-cards badge** on the FAB that *also* opens the picker on tap (novices see it; power
  users ignore it and long-press), and (b) a **one-time coach hint** ("Hold to choose how you
  study") the first time the FAB is used. Either route reveals the deliberate path — the
  context-worthy mode chips (§6), the current sheet's *content* reframed, not a flat list.
- **Empty state:** when `next-action` is `null` (no concepts yet), the FAB's default routes to
  capture ("add material") instead of an empty study surface — mirrors the home empty state.

## 5. Session as a flow (not one-and-done)

Today a challenge is a dead-end: answer → result → back. The spec's session model
([system-spec §5]) is a **bout** the app clusters automatically (≥15-min idle gap ends one),
ending with a **warm close** ("you firmed up 4 concepts; X is still shaky; recap tomorrow?").

So retrieval should **flow**: `next → answer → result → next…` interleaving due concepts,
until the user stops or the queue empties. This is exactly what **"keep going"** enables —
now unblocked because `POST /next` returns `concept_text` (backend change 2026-07-30), so each
next challenge is correctly labeled.

- **Continuation:** after a result, "Keep going" pulls the next due concept in the topic
  (engine-selected, no `concept_id`), labeled by its own `concept_text`.
- **Close:** when the queue empties (or the user ends), show the warm close — lead with growth,
  whisper the fading (system-spec §6 framing), offer the next hook (recap tomorrow).
- **Calibration** is the quiet signature metric surfaced at the close, not per-attempt nagging.

The `GET /sessions` endpoint already derives sessions from the attempt log for a history view.

## 6. The mode picker, done right (the deliberate path)

Keep the ability to choose — the LOCKED constraint was against *redesigning it as-is into a
better list*; this replaces the list with something context-worthy:

- **Scope-filtered:** show only modes that fit the current scope. Concept in hand → quiz /
  pretest / ramble / teach. Whole topic → dump. Last session → recap. Never offer a
  concept-mode when there's no concept, or a topic-mode with no topic.
- **Affinity-ordered:** `GET /modes?family=` returns each mode's affinity for the topic's
  subject family (STEM ranks worked/quiz; humanities ranks ramble/teach). Order the chips by
  it; the top chip is the engine's recommendation, visually distinguished.
- **Contextual copy:** each chip says what it'll do *to this concept*, not a generic blurb.

This is the same data the fast path uses — the deliberate path just exposes the ranking instead
of acting on it.

## 7. Backend support — what exists vs. gaps

**Already built (no new work):**
- `GET /next-action` (+ `?course_id=` / `?topic_id=`) — the doorway; kind cascade
  review→calibration→dump→new→get_ahead, subject-aware `mode`, warm `reason`, `est_minutes`.
- `GET /modes?family=` — per-mode affinity (the ordering knob).
- Scoped challenge surfaces: `/next` (concept), `/dump` + `/recap` (topic/session).
- `GET /sessions` — session history from the attempt log.
- `POST /next` now returns `concept_text` (2026-07-30) — unblocks labeled continuation.

**Gaps to build:**
- **Warm-close data — DECIDED 2026-07-30: a backend session-summary derive** (not client-side).
  New endpoint (e.g. `GET /api/retrieval/session-summary?topic_id=` or a POST that closes the
  bout) returning what the session changed — concepts firmed / still slipping / calibration
  delta — from the attempt log, reusing the `GET /sessions` clustering (≥15-min idle gap). TDD
  vs. real Postgres, per convention. This is the one net-new backend piece the redesign needs.
- **`next-action` freshness** — it reads live (uncached); confirm it re-picks correctly after an
  attempt so the home hero advances rather than re-offering a just-done concept.

## 8. What's already wired (so the redesign builds on real data, not mock)

- **`retrieval.tsx`** — the real two-request session (next → confidence → attempt → outcome +
  calibration + schedule; worked-STEM reveal; recap/dump). Modes driven off `GET /modes`.
  (See the 2026-07-29 log entry in the integration plan.)
- **`concept_text` on `/next`** (backend, 2026-07-30) — labeled continuation; test added.
- **"Keep going"** re-enabled in `retrieval.tsx` — the seed of the session flow (§5).
- **Home hero → `GET /next-action`** (2026-07-30) — the fast path's first surface: engine picks
  kind/mode/topic, one tap opens the right challenge; caught-up + no-concepts states handled.

So the fast path already exists on home and in the note. The redesign is mostly the **FAB
rework (§4)**, the **session flow + warm close (§5)**, and the **context-worthy picker (§6)**.

## 9. Per-mode interfaces — each mode is its own experience (must be built)

**The current `retrieval.tsx` renders every mode through one generic renderer** (a prompt +
MCQ buttons / a textarea / worked-reveal / a per-concept table). That was the wiring pass — it
proves the loop, but it is *not* the finished experience. A core premise of the redesign: **each
mode is a distinct interface**, because each is a different cognitive act. These need designing
and building, not just wiring:

| Mode | The act | Interface wants |
| --- | --- | --- |
| **Quiz (MCQ)** | Recognise the right answer | Clean options; instant reveal + why-wrong |
| **Quiz (short/essay)** | Produce a written answer | Focused writing surface; AI feedback + missed points |
| **Pretest** | Guess *before* studying | Framed as low-stakes ("a guess is fine"); calibration is the payoff |
| **Ramble** | Say everything, uncued | **Voice-first** big open surface; talk until you run dry |
| **Teach** | Explain to a novice | An *audience* cue (teach "someone who's never seen it"); rewards clarity |
| **Worked (STEM)** | Solve on paper, self-grade | Math rendered as math; predict → reveal → 4 honest buttons; optional photo of work |
| **Recap** | Free-recall last session | One response, many concepts; per-concept result map |
| **Dump** | Empty the whole topic, uncued | A big blank canvas; nothing listed (listing = handing back the answer) |

Cross-cutting inputs these interfaces depend on (both currently deferred, see integration plan
§2.7): **voice** (`/ws/voice`, §2.8 — ramble/teach/dump shine here) and **paper photo**
(`/transcribe`, B8 — worked/dump). The mode interfaces and these input surfaces are coupled;
plan them together.

## 10. Decisions log (settled 2026-07-30)

1. **Doorway** — engine-chooses by default, pick as the expand. ✅ (§2)
2. **FAB "pick" affordance** — long-press **+** a visible caret/badge + one-time hint (so the
   gesture is discoverable). ✅ (§4)
3. **Warm close** — **backend** session-summary derive, not client-side. ✅ (§7)
4. **FAB vs. per-surface entries** — **coexist**: per-surface entries (home hero, note tap)
   stay; the FAB is the *global* "study now" for when you're not on a content surface. ✅
5. **Draggable persistence** — per-device local for launch (not synced). ✅ (low-risk default)

## 11. Build order

1. ✅ **Warm-close backend derive** (§7) — DONE 2026-07-30. `services/retrieval/session_summary.py`
   (`build_session_summary` over the last session's raw attempts — `session.last_session_attempts`
   added; firmed=solid / slipping=shaky·fading via `derive_mastery`; calibration delta) +
   `GET /api/retrieval/session-summary` (uncached, per-user, enrollment-gated on `course_id`).
   10 tests (6 service + 4 API), no model change / no migration.
2. ✅ **Session flow + warm close** in `retrieval.tsx` — DONE 2026-07-30. "Keep going" now runs a
   real bout (engine-selected next due concept); "Done for now" or an exhausted queue (404) flows
   into the **warm close** (`CloseView`): growth-led headline, whispered slipping, calibration
   line, recap-tomorrow hook. `fetchSessionSummary` in `lib/retrieval.ts`.
3. **Per-mode interfaces (§9)** — build each mode's real experience, one at a time. ← **in progress**
   - ✅ **Worked / STEM (self-calibration)** — DONE 2026-07-30. Math rendered as math (reuses the
     note's `MathBlock` SVG + Unicode-inline via a new `components/retrieval/MathText.tsx`) in the
     problem, the revealed solution, and result feedback; "solve on paper" framing; confidence
     *before* reveal copy; reveal → 4 honest self-grade buttons → self-graded result headline;
     numeric STEM = typed-number "Check". No backend needed (the worked flow was already backed).
     **Deferred:** the *optional* photo-of-work attachment (spec §5 — never required for self-grade;
     no attempt-image endpoint exists) → folds into the paper-input surface with dump/ramble.
   - ✅ **Paper input surface (`/transcribe`, B8)** — DONE 2026-07-30. A shared
     `components/retrieval/WrittenAnswer.tsx` (Textarea + "snap your handwriting"): photo →
     server transcription → drops into the *editable* field (correcting the text **is** the
     confirm step) → submits as text with `answer_origin:"paper"`. Wired into **every written
     mode at once** — dump, recap, ramble, teach, and quiz short/essay — since the substrate is
     "any written answer, any mode." `transcribePaper` in `lib/retrieval.ts` (raw `fetch` + manual
     JWT: SDK-57 winter multipart needs Blob-compatible expo `File` parts, not axios). Reuses the
     already-installed `expo-image-picker` (`takePhoto` burst) + camera perms from capture.
   - ✅ **Voice input (on-device STT)** — DONE 2026-07-30. A "🎤 Speak" button in `WrittenAnswer`;
     `useVoiceDictation` (`expo-speech-recognition`) transcribes **on-device** (offline, free, live
     partial results) straight into the editable field — the confirm step is the same edit-before-
     grade as paper. **Not premium** (the *generated audio* / listen mode is the premium lane, a
     separate later integration — not this). Available in every written mode. Submits as plain text
     (the grader's voice-leniency is challenge-driven, so no per-attempt marker needed).
     Considered + rejected server Whisper (better jargon accuracy, but loses live/offline and needs
     upload+cost); the editable confirm covers STT slips. **Owner:** new native dep
     `expo-speech-recognition` + a config-plugin (mic/speech perms in `app.json`) → **rebuild the
     dev client**; accuracy varies by OS.
   - ⬜ **Quiz (short/essay) / Pretest** — functional (now with paper + voice input too); a further
     bespoke pass is lower priority.

   With STEM, paper, and voice done, **the written/STEM modes are substantially complete.** Next is
   step 4 (context-worthy picker).
4. ✅ **Context-worthy picker (§6)** — DONE 2026-07-30. The in-session mode picker now orders modes
   **best-fit-first** for the topic's subject and **badges the top one "Best fit"**, with a "Ranked
   for this {STEM/humanities/language} topic" header — the recommendation leads, it's no longer a
   flat list. Driven by the topic's `subject_profile.mode_mix` (`fetchTopicProfile` →
   `GET /topics/{id}/profile`, one call gives family + affinity for all six modes; brain dump keys
   as `brain_dump`). Best-effort: falls back to default order if the profile can't load. Layout
   otherwise unchanged (still the sheet) — this is the "context-worthy" the parked §1 complaint
   asked for; relocating/spreading it across surfaces is the FAB work below.
5. ✅ **FAB rework (§4)** — DONE 2026-07-30. `NavFab` rebuilt from a scope-less flat mode list (which
   routed `/retrieval?mode=X` with no topic → hit the "open a note" guard) into the **engine-chooses
   doorway**: **tap = study now** (`GET /next-action` → `/retrieval` with the engine's topic/concept/
   mode, or `/courses` when nothing's due); **long-press = the pick menu** (the next-action's `reason`
   as context, "▶ Start — {mode}", then mode-override rows that keep the engine's WHAT and change only
   HOW, + Home). **Draggable** (PanResponder + Animated, on-screen-clamped, position persists across
   route changes via module state — cross-restart persistence is a flagged follow-up). One-time
   **hint** ("Tap to study now · hold to choose how"). Hidden on `/retrieval` itself. No new deps
   (RN core), so no rebuild for this. Dropped the phantom "Timed test" entry (testbuilder's, not a
   retrieval mode).
6. ✅ **Course/topic-page entry** — DONE 2026-07-30. `topics.tsx` (the course page) now shows a
   course-scoped **"Study now" card** driven by `GET /next-action?course_id=` — the highest-value
   thing to do in *this* course (topic + warm reason + est), one tap into the engine's pick. Hidden
   when nothing's due. Same launch contract as the home hero + FAB.

**The build order is complete** — all six steps shipped. Retrieval is now an engine-chooses,
context-worthy, ambient surface (home hero, course page, note-tap, global FAB), with a real session
loop (warm close), STEM/paper/voice input, and a best-fit-ranked picker. Remaining polish is tracked
inline above (cross-restart FAB persistence; affinity-ordered chips inside the FAB menu; the optional
worked-photo attachment) — none blocking. **Social-sciences subject family shipped 2026-07-30**:
`SubjectFamily.SOCIAL_SCIENCE` (theory+evidence — teach-led, quiz stays solid for named
theories/studies), profile + synthesis lean + classifier line + mobile label + enum-add migration.

**Next major thread — conversational modes (teach · ramble).** Designed in
[`conversational-modes.md`](conversational-modes.md) (escalate-first): both go multi-turn, the mode
boundary grows `open/turn/close`, one FSRS grade still commits at close, 7-turn cap. Not built.

Each ships one surface/mode at a time, behind the existing "flag drift, don't fake" rule, per
the integration plan's top-of-doc convention.
