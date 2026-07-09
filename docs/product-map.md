# NotesOS — Product Map (where we want to be)

> **Living document.** The target product surface — the territory we're building
> toward, and where we are on it today. This is the *what we want to exist*; the
> *why* lives in [`NotesOS_Architecture_NextPhase.md`](../NotesOS_Architecture_NextPhase.md)
> and [`Learning_Science—NotesOS_Design_Constraints.md`](../Learning_Science—NotesOS_Design_Constraints.md),
> the *build/status* in [`v2-redesign-plan.md`](./v2-redesign-plan.md).
>
> UI is out of scope here on purpose — the designer owns the surface. Our job is to
> make sure the backend is right so the designs plug straight in. **Backend leads,
> design follows.**
>
> Last updated: 2026-07-05.

Legend: ✅ have it · 🟡 partial · ⬜ gap · 🔮 deferred (real, but not now)

## The stance

Two commitments shape every feature:

1. **Helps you, doesn't lie to you.** The enemy is the fluency illusion — feeling
   like learning without it happening (Learning Science Parts 3–4, 13). NotesOS
   refuses to let you *feel* mastery you can't demonstrate. Retrieval and
   calibration are how it keeps that promise.
2. **Very, very communal.** Every other study app is solo. NotesOS's bet is the
   group — shared notes, shared retrieval, and everyone who contributes *feeling
   seen*. The social layer is the moat and the retention mechanism (Parts 14–15),
   not a nice-to-have.

## The core architectural bet

**The retrieval engine is not "quizzes." It is a set of pluggable retrieval *modes*
over one shared substrate.**

```
Retrieval Engine = {modes} × {subject weighting} × {scope} × {per-concept state}
```

Quiz, ramble, teach, pretest are not separate features — they're different ways to
trigger recall. Get this abstraction right and every mode (now and future) is a
*plugin*, not a rebuild. This is why the engine has to be robust: it's the center
of gravity for the whole product.

- **modes** — how recall is triggered (see below).
- **scope** — the pool a session draws from: single topic · whole course ·
  *interleaved mix* (Part 2) · *spaced-due* (Part 5).
- **subject weighting** — which modes/sub-types a subject favours (Part 12).
- **per-concept state** — the substrate every mode reads from and writes to (§ below).

### Retrieval modes

| Mode | What it is | Science | Status |
|---|---|---|---|
| **Quiz** | Structured Q&A. Sub-types: recall · "why"/elaborative · applied-problem | Parts 2, 3, 9, 12 | 🟡 plugin on the engine; still one flavour |
| **Ramble / Talk** | You speak freely about a concept; AI asks leading Socratic questions to surface gaps. Free recall + elaborative interrogation — stronger than cued recall | Parts 3, 9 | 🟡 single-shot plugin (open prompt → gaps); multi-turn Socratic later |
| **Teach / Protégé** | You explain the concept to the AI (or to publish). Teaching forces retrieval + reorganization + gap-finding. A good explanation can become a note **contribution** | Part 15 | 🟡 single-shot plugin (correctness-capped scoring) |
| **Pretest** | Questions *before* encoding — on add, or mid-study. Primes encoding, breaks the fluency illusion early, feeds calibration | Parts 12, 4, 8 | 🟡 plugin (quiz reuse, grade capped so a pre-study guess can't schedule far out) |
| **Recap** | At the start of a study block: "blurt everything you remember from last time." Free recall of the *previous session* — spaced retrieval + distributed practice in one warm-up move | Parts 5, 3, 9 | ⬜ (session-scoped, see note) |
| *(Listen)* | Passive reinforcement, not retrieval — the spacing/consolidation touchpoint. Lives in Delivery | Part 10 | ✅ |

> **Recap is session-scoped, not concept-scoped** — the first mode where *one* response
> is graded against *many* concepts (the set the last session covered), producing an
> attempt per concept. It stretches the pass-1 Protocol (`generate(concept)` → one
> attempt) in the orthogonal direction to multi-turn Socratic: many concepts / one turn
> vs. one concept / many turns.
>
> **Session definition — LOCKED (2026-07-09):** a study session **is a bout of
> retrieval** — nothing else counts as "studying" (rereading the note is the fluency
> illusion; only retrieval is real study, so only retrieval opens a session). A bout is
> a run of `RetrievalAttempt`s clustered by idle gap: **a gap ≥ 15 min closes the
> session.** Derived from the append-only attempt log — **no session table on day one**;
> materialise later only if history/UX earns it. Listen is a legitimate *second* session
> type later (retrieval-after-listening is the testing effect on fresh input), but v1 is
> retrieval-only.
>
> **Recap scoping:** "last session" spans whatever you touched, so **spanning is the
> general case and topic-scoped is a filter on it.** Build **topic-scoped first** (obvious
> home — reopening a topic; easier same-topic grading), then full-session recap is the
> same machinery with the topic filter removed. Recap is **offered, never forced**
> (notebook ethos, same instinct as notify-don't-enroll) — a persuasive reject-twice
> nudge ("recapping what you learnt strengthens it"), a UI concern.
>
> **Shared keystone:** the session concept is the foundation recap *and* multi-turn
> ramble/teach both stand on — build it once, deliberately, here.

Ramble, teach, and voice-quizzes all ride the **same voice substrate** (transcription
→ grading). Optimizing voice is foundational to three modes at once, not quiz-specific.

## The spine — the loop one student walks

1. **Capture** ✅🟡 — upload (text/PDF/DOCX/images), hybrid OCR, chunking, embeddings.
   *Aim:* reliable on real student mess, no manual cleanup.
2. **Synthesis — the Consolidated Note** 🟡 *(the wedge)* — synthesized note + key
   points + fact-check. *Aim:* provably better than any single source; trustworthy;
   shows who contributed; protected by the merge/quarantine gate (Phase 4). Becomes
   a **multi-modal canvas**: text + embedded topic video (🔮) + inline retrieval +
   chat in one view (dual coding, Parts 1, 5).
3. **Retrieval Engine** 🟡 — see the core bet above. The center of gravity.
   *Built (pass 1):* the three-table substrate (Concept / ConceptState /
   RetrievalAttempt), FSRS scheduler, mode Protocol + engine core (scope selection /
   attempt recording / scheduling), concept extraction wired into synthesis, and the
   **quiz migrated onto it as the first plugin**. *Built (pass 2):* ramble / teach /
   pretest as single-shot plugins, the HTTP session surface (`POST /api/retrieval/next`
   → `/attempt`), per-attempt calibration (predicted vs actual), and the dormant
   recognition seam (topic-level attribution, gated behind `ENABLE_RECOGNITION`).
   *Next:* multi-turn Socratic ramble/teach, subject-aware mode mixing, and wiring
   recognition live once §11 attribution + §9 digest land.
4. **Learning-science layer** ⬜ *(rides on §per-concept state)* — spaced repetition ·
   calibration (predict-vs-actual) · forgetting history / durability ·
   **knowledge-decay as the headline metric, not streaks** (Part 13) ·
   difficulty-as-a-feature framing (Part 6).
5. **Delivery** 🟡 — Listen mode, note reading, AI tutor chat. *Aim:* multi-modal by
   default · Listen as the daily spacing touchpoint · **micro-entry point** (one card)
   to kill starting friction (Part 11) · timing/sleep-aware (🔮, Part 10).

## The communal layer — what makes it NotesOS

6. **Contribution visibility** ⬜ — the *static* picture: "12 classmates built this
   note; you've added 0." Social proof + anti-social-loafing accountability, without
   a leaderboard (Part 15). We store `uploaded_by`; we never surface/aggregate it.
7. **Recognition loop** ⬜ *(moat pillar)* — the *dynamic* signal: your work was just
   used → you're seen → you contribute more → the shared note improves → flywheel.
   Fires when someone benefits from you: takes your quiz, reads your note, tests
   after reading, you were first into a topic. Same lever as the governance
   regulator ("name on it") — the positive side. **Needs an attribution/consumption
   data layer** linking every consume event back to a contributor.
8. **Discovery & coordination** — discovery + proximity ✅ (Phases 2–3);
   coordination ("someone's building a test, want in?") 🔮.
9. **Notifications** 🟡 — the delivery channel for 6/7/8 **and** spacing nudges
   ("5 days since you reviewed X"). *Aim:* preferences + **digest/batching** so it's
   signal not spam; **aggregate + anonymous for passive consumption** (reads),
   warmer and specific for active (took *your* quiz) — seen, not surveilled.

## The substrate — invisible, load-bearing

10. **Per-concept knowledge state** ✅ *(the unlock — built pass 1)* — every recall attempt,
    timestamp, right/wrong, predicted-vs-actual, per user per concept. Today we only
    have per-*topic* mastery. Build this and most of §4 becomes scheduling on top of
    data we already capture. **Single highest-leverage thing on the map.**
11. **Attribution / consumption events** ⬜ — powers the recognition loop (§7) and
    contribution visibility (§6). Consume events tagged with who-made-the-thing.
12. **Trust / governance** 🟡 — proximity ✅ · merge/quarantine gate ✅ (Phase 4:
    off-topic uploads held out of the shared note, uploader-only, auto-released on
    corroboration) · attribution surfacing ⬜ · corroboration weighting ⬜.
13. **Offline + sync** 🔮 *(native, later — but shapes §10 now)* — design the
    retrieval substrate sync-friendly so we don't repaint later.

## Cross-cutting

- **Subject-awareness** — not a feature, a *knob on the engine*. Content-heavy
  (history, journalism) favours why-questions + ramble + teach; STEM favours pretest
  + applied problems + worked-example-then-vary; language favours output (ramble,
  production). Same engine, different mode mix (Part 12).
- **Voice substrate** — shared by every voice mode; optimizing it lifts all of them.

## Design tensions to hold (getting these wrong makes it feel *worse*)

- **Kudos warmth vs. creepiness.** Recognition must feel like a study group noticing
  you, not surveillance. Aggregate passive reads; personalise active engagement.
- **Notification signal vs. noise.** Digest and batch, or the whole loop gets muted.
- **STEM grading is genuinely hard.** Grading an applied problem (method vs. answer,
  partial credit) is a different beast from checking factual recall. "Subject-aware
  for STEM" is real engineering, not a toggle — scope it honestly.
- **Difficulty as a feature.** Retrieval *should* feel hard (Part 6). The product has
  to frame hardness as the mechanism, or users read it as broken.

## Core vs. later (a starting read, not a verdict)

- **Core — "helps you, doesn't lie" heart:** Capture, Synthesis, Retrieval Engine
  (with ramble/teach/pretest as first-class modes), per-concept state, and the honest
  metric spine (calibration + decay).
- **Core — "it's *NotesOS*" heart:** Contribution visibility + Recognition loop +
  the communal reach of Notifications.
- **Deferred without guilt (🔮):** video embed, offline/sync, coordination mode,
  timing/sleep-aware delivery, speech-emotion-as-calibration signal, deep
  subject-awareness for STEM.

## Deferred idea log

- **Video embed** — backend fetches/selects 1–2 YouTube links for a topic, note
  embeds them. Simple version only. Low-lift when we get to it.
- **Speech-emotion signal** — read hesitation/confidence from voice as extra
  calibration data. Interesting, overreach-prone, later.
