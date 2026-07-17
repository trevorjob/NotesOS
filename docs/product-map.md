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
> Last updated: 2026-07-10.

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
| **Recap** | At the start of a study block: "blurt everything you remember from last time." Free recall of the *previous session* — spaced retrieval + distributed practice in one warm-up move | Parts 5, 3, 9 | ✅ (A3 — orchestration over the session's concept set) |
| **Brain dump** | "Everything you know about this topic" — **uncued, whole-topic free recall.** The purest retrieval act: no concept cue at all; one monologue graded against the topic's full concept set, missing concepts are genuine lapses | Parts 3, 9 | ⬜ (recap's machine, topic-set selector — see note) |
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
>
> **Brain dump — LOCKED (2026-07-17).** Brain dump and recap are **two surfaces of one
> free-recall machine**, distinguished only by the *set selector*:
>
> - **Recap** = last **session's** concepts ("blurt everything from last time") — built (A3).
> - **Brain dump** = the **topic's full** concept set ("everything you know about this
>   topic") — uncued whole-topic free recall, the purest retrieval act on the platform.
>   A concept the monologue never surfaces is a genuine lapse, exactly as in recap.
>
> No new machinery: `grade_recap` already takes an arbitrary `concept_ids` set and
> batch-grades one monologue into an attempt per concept — brain dump is a new selector
> + a distinct mode key (`brain_dump`; **not** "dump", which capture already uses).
> Owner-validated tactic (dogfooding, 2026-07): *read once → dump → leave → dump again
> hours/days later → reread → dump*. That **protocol is a schedule, not a feature** —
> the spacing beat is FSRS/`spaced_due`/decay-nudge, and the dump-before-rereading beat
> is the next-best-action's job for a freshly-read topic. The entry point teaches the
> rhythm; the user never has to learn it by name.

Ramble, teach, and voice-quizzes all ride the **same voice substrate** (transcription
→ grading). Optimizing voice is foundational to three modes at once, not quiz-specific.

> **Paper substrate — LOCKED (2026-07-17).** The written twin of the voice substrate: any
> written answer, in any mode, can be a **photo of handwriting** (B8). One transcription
> pre-step (server vision → user **confirms/corrects** → the unchanged text `/attempt`),
> so all modes get it at once — including handwritten brain dumps, the paper-native study
> pattern the product refuses to fight. Fairness rule: **grade what the user confirms
> they wrote, never what OCR guessed.**

## The spine — the loop one student walks

1. **Capture** ✅🟡 — upload (text/PDF/DOCX/images), hybrid OCR, chunking, embeddings.
   *Aim:* reliable on real student mess, no manual cleanup. Design locked below.

> **Capture — design LOCKED (2026-07-11).** Governing rule: **"studying is hard; everything
> else is dead simple."** Capture is the **silent ceiling** (garbage in → wrong note → wrong
> concepts → wrong quizzes) *and* where friction most starves the communal note. Today accepts
> images/PDF/DOCX only; vision path (`vision_transcribe`, GPT-4o) handles slides/whiteboards/
> handwriting. Four moves:
>
> - **Audio / lecture capture — build it (biggest missing surface).** You can't record/upload
>   a lecture → notes today, yet `transcription.py` (Whisper) already exists (wired only to
>   *grade voice answers*). Expose it as ingestion: in-app record or audio upload → Whisper →
>   same chunk→synthesize pipeline. High value, plumbing mostly built.
> - **Preserve visuals (root of STEM parity).** The pipeline flattens everything to *text* —
>   figures, diagrams, equations, structures, graphs lost as visuals. Fine for humanities,
>   **crippling for STEM** (the diagram *is* the content). Keep figures attached + referenced
>   inline (feeds the multi-modal note and STEM parity). STEM's gap is *born here in capture.*
> - **Flag low-confidence OCR** — a blurry scan must not launder into confident-wrong shared
>   notes ("this page was hard to read — check it?"), not silent acceptance.
> - **Dump-then-auto-organize — never block capture on organization.** *This is the founder's
>   own pain* (dreads uploading a semester because v1 makes you file each note into a topic).
>   Split the two acts: **capture = instant + dumb** (throw the whole pile in, one action, zero
>   filing); **organization = deferred + smart** (system sorts the pile into topics). Friction
>   collapses from "course → topic → file ×N" to **"course → dump → confirm."**
>   - **Two entry points — the destination is implied by *where you add from* (don't forbid
>     filing, just never force it).** *Course-level add* = unsorted pile, destination unknown →
>     auto-organize → confirm. *Topic-level add* (you're inside "Programming Languages," hit add)
>     = destination known → **straight in, no sorting, no confirm.** Navigating to a topic *is* a
>     cheap, natural act of organizing — honor it, don't override it. (A direct-add that clearly
>     doesn't fit gets a **gentle flag** — "looks like X, move it?" — a suggestion, never a block.)
>   - **Course-outline scaffold (when available).** Paste/snap the syllabus → system creates the
>     canonical topics up front. This turns auto-filing from **clustering** (invent + name +
>     assign — error-prone, the misfiring risk) into **classification** (assign each file to one
>     of N *known* buckets — reliable; worst case is a one-drag fix). **Outline when you have
>     one, auto-cluster + propose when you don't** — same "use structure when present, degrade
>     gracefully" philosophy as the emergent set; the outline is optional metadata.
>   - **Bonus powers of the outline:** it's a **communal artifact** (one person adds it → whole
>     class inherits the canonical skeleton → clean cross-student merging); **coverage tracking
>     for free** ("materials for 6/10 topics; Aromaticity empty" — pre-exam completeness); a
>     **roadmap** of upcoming topics (enables pretest / pre-class head-starts).
>   - **Course stays the one manual step**, topics fully auto; **course-level dump** is the entry
>     (a true no-course "unsorted inbox" is a lovely later addition). Confirm step is
>     **review-and-adjust (opt-out)**, never file-it-yourself — nail the default so most just tap
>     accept.
2. **Synthesis — the Consolidated Note** 🟡 *(the wedge)* — synthesized note + key
   points + fact-check. *Aim:* provably better than any single source; trustworthy;
   shows who contributed; protected by the merge/quarantine gate (Phase 4). Becomes
   a **multi-modal canvas**: text + embedded topic video (🔮) + inline retrieval +
   chat in one view (dual coding, Parts 1, 5). Design locked below.

> **The Consolidated Note — design LOCKED (2026-07-11).** Today it's one
> `TopicKnowledge` row (a `consolidated_note` markdown blob + `key_points` + `concepts`
> + `source_count`), **fully rebuilt from all chunks on every upload**. Good summary,
> wrong shape for the wedge. The reframe and the four moves:
>
> - **The Note is a launch point, not a destination.** A note is a *reading* surface, and
>   reading-*instead-of*-retrieving is the fluency illusion (§stance 1) — so the Note must
>   be good enough to pull people in *while refusing to let them mistake reading it for
>   knowing.* "Make it good" ≠ "nicer document"; it means the front end of the retrieval
>   engine. (Reading itself stays — knowledge has to get in before it can be pulled out;
>   we're anti-*only*-reading, not anti-reading.)
> - **Incremental append, not rebuild.** New material **merges into the existing note**
>   rather than regenerating it from scratch. Fixes the write-amplification cost bomb
>   (full re-synthesis over a growing chunk set, every upload) *and* unlocks "what changed
>   since you last read" (retention) and "Ada added this section" (recognition, made
>   visible on the note).
> - **Active surface — wire the note to the Concept substrate.** We already elevate
>   `concepts` into first-class `Concept` rows with per-user mastery state; the *note text*
>   isn't linked to them. Link it, and the note becomes a live map: terms light up by
>   what you know vs. what's decaying, tap a paragraph to be retrieved on it *right there*,
>   reading flows into retrieval with no screen change. This is the anti-fluency-illusion
>   mechanic built *into* the reading surface — it catches you the moment you mistake
>   reading for knowing. **This is the thread to lean into.**
> - **Trust = invisible plumbing + on-demand X-ray, never a debate.** The note is *always
>   one authoritative voice.* **No inline conflict display** ("Source A vs B — they
>   disagree" dumps adjudication back on the reader, which is the exact work the note
>   exists to do for them). Instead: (a) corroboration weighting works **silently at
>   synthesis** — when sources conflict, the note commits to the better-supported answer
>   and moves on, just quietly more right; (b) a **"says who?"** tap X-rays a single line's
>   provenance *on suspicion*, for the skeptic only; (c) **"your cohort built this"** stays
>   as a warm *social* trust signal (real classmates, not a faceless AI) — a different
>   animal from conflict display.
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
   **knowledge-decay as the headline metric, not streaks** (Part 13 — decay is also the
   honest-loss-aversion engine behind the §9 habit model) ·
   difficulty-as-a-feature framing (Part 6). Progress-display model locked below.

> **Progress without streaks — LOCKED (2026-07-11).** A streak does two jobs — it's the
> **metric** *and* the **hook** — and that fusion is why it's dishonest (as a metric it
> measures showing-up, not knowing) and punitive (as a hook it's a fragile chain that
> shatters on one miss). **The escape: split the two jobs.** The §9 decay nudge + the §5
> one-card home already *are* the hook, so the progress surface is **freed from having to
> manipulate** — it gets to be the one thing a streak never is: just *true*.
>
> - **Headline = your living knowledge state** (concepts solid / fading / shaky, moving in
>   real time). Structurally the opposite of a streak in the humane way: **continuous and
>   forgiving** (a concept fades *gradually*, *any* retrieval revives it, no cliff, nothing
>   you can "break") vs. streak's **binary and fragile**. That's honest loss-aversion
>   *without* the anxiety — wilting is gentle and reversible; a broken streak is final.
> - **Framing balances gain *and* loss.** Losing is the stronger pull, so we don't deny it —
>   but **lead with growth, whisper the fading** (not anxiety-farmed). "4 got more durable
>   today" foregrounded; "3 are slipping" present but gentle.
> - **Progress is spatial, not a scoreboard.** The **active-surface note lit by mastery IS
>   the progress map** (reuses the note↔concept linking) — solid terms glow, fading ones dim;
>   you see your knowledge *across your own notebook*, not as a vanity number. A dedicated
>   stats view is optional *depth*, never the headline. (Delivers §5's "glimpse, not a
>   dashboard.")
> - **Calibration is the signature-but-quiet metric** — *"getting better at knowing what you
>   actually know"* (predicted-vs-actual, already computed). The purest expression of "doesn't
>   lie to you," the meta-skill no competitor shows — but surfaced **when needed, not in your
>   face.**
> - **Difficulty-as-a-feature, made visible** — celebrate the productive struggle ("that was
>   hard, which is why it stuck"), so hardness reads as the mechanism, not breakage.
> - **No comparison, no leaderboard** — progress is personal and absolute; the social layer is
>   *contribution*, never a knowledge-ranking.
5. **Delivery** 🟡 — Listen mode, note reading, AI tutor chat. *Aim:* multi-modal by
   default · Listen as the daily spacing touchpoint · **micro-entry point** (one card)
   to kill starting friction (Part 11) · timing/sleep-aware (🔮, Part 10). Daily-entry
   design locked below.

> **The daily entry point — LOCKED (2026-07-11).** We design the *service*, not the pixels
> (designer owns the surface): a **next-best-action engine** answering *"the single
> highest-value thing you could do in the next 5 minutes."* The UI renders one card's worth.
>
> - **Doorway, not dashboard.** The most-abandoned moment in studying is *deciding what to
>   study* — a menu of courses/topics/modes is friction at the threshold, where sessions die
>   before they start. The home's most valuable act is **removing the choice**: one card, one
>   tap, decision already made.
> - **The home *is* the decay digest, pulled instead of pushed.** Same selector that powers
>   the §9 decay **notification** (push — reaches your pocket) renders the **home card** (pull
>   — waiting when you open cold). **One next-best-action engine, two channels** (reads
>   FSRS due-state + calibration gaps + what's new). Build once.
> - **A hero card, not a stack** — a prioritized *list* re-introduces the choice we're killing.
>   Quiet "or something else ↓" for the self-directed, but one thing leads.
> - **Under-promise the entry.** Promise something *tiny* ("one question," "2 min") — the
>   friction is *starting*; momentum extends the session once in. "34 due!" triggers avoidance.
>   Small door, big room.
> - **Context-aware entry:** from a nudge → drop **straight into** the promised session (no
>   re-navigation); cold → hero card waits; inside a topic → offer **recap**.
> - **Review is the default hero; new is a distinct, secondary surface.** *New* (classmate
>   uploaded, note grew, recognition) is clickier; *review* (decayed concepts) is more
>   valuable. Letting new win the top slot builds an engagement toy and buries the honest
>   work — so review leads, new gets its own place. This is the "helps you, doesn't lie" line
>   at the front door.
> - **Never empty-handed.** Nothing-due can't read as "nothing to do" (churn signal) — falls
>   back to pretest something new / get ahead / explore a fresh upload.
> - **A glimpse, not a dashboard.** Progress shows as gentle invitation ("your Krebs cycle is
>   fading"), never a stats wall (friction) or guilt — carries into the progress model below.

> **Listen mode + AI tutor — LOCKED (2026-07-11).** These are the two **passive** surfaces
> (you consume, don't produce) — where the fluency illusion lives. Governing principle:
> **retrieval is concentrated in the modes; the support surfaces stay low-friction and get
> out of the way** — don't spread the "make them work" instinct across every surface.
>
> *Listen* (today: `audio_worker` batch-generates one `AudioLesson` off the note):
> - **Lecture style — NOT podcast/two-voice** (explicitly rejected, twice). It's
>   spacing/consolidation **reinforcement, not retrieval** (Part 10), and the lowest-friction
>   surface (commute/walking/dishes). Honest about not building durability like retrieval does.
> - **Rotate a few variations.** Users report the single audio goes stale after a few listens.
>   Fix = generate **several lecture variations and rotate** them — deliberately **cheap/light**
>   (it's passive reinforcement, shouldn't eat much cost). *Not* the personalized route for now.
> - **Active-listen seams** (some already built, improvable): audio pauses → asks → you answer
>   **out loud** (voice substrate). Testing effect embedded in a lecture — off by default so the
>   low-friction version stays low-friction.
> - *Deferred (premium):* personalized gap-review Listen (reads `ConceptState`, dwells on
>   what's fading) — the audio arm of the decay engine. Not now (TTS is per-char pricey, doesn't
>   amortize per-user).
>
> *AI tutor* (today: `study_agent`, chat over the material):
> - **Just answers — a fast utility, NOT Socratic.** The Socratic/retrieval pressure already
>   lives in the modes; the tutor's job is a quick explainer / fast lookup to **unblock you and
>   get out of the way.** Making you work again when you need a quick answer is friction in the
>   wrong place.
> - **State-aware** — knows your notes **+ ConceptState**, so it pitches the explanation to your
>   level (the moat over generic ChatGPT-with-notes) — but it answers *directly*.
> - **Connective tissue** — reachable from everywhere (inside the note, after a wrong answer,
>   mid-Listen), always carrying the context of where you invoked it.
> - **Where the brand voice lives** — "brilliant, slightly irreverent study partner"; the
>   personality settings are its tuning knobs.

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
   coordination ("someone's building a test, want in?") 🔮. Synchronous-communal stance below.

> **Trust & safety + store compliance — LOCKED (2026-07-17).** Three calls made for the
> app-store launch (full checklist: `launch-readiness.md`; buildable items: Phase D):
>
> - **iOS auth is phone-only** — no Google button on iOS, so Apple's Sign-in-with-Apple
>   obligation never triggers. Android/web may keep Google.
> - **Report → quarantine → owner review.** Anything shared is reportable (including AI
>   output); a report holds the content out of the shared surface via the existing
>   merge-gate machinery — no moderator roles, no public drama, reporter anonymous.
>   Blocking is a **personal view filter**, never a takedown. Governance stays ownerless;
>   the owner-review step is an ops process, not a role in the schema.
> - **Account deletion is real and findable** — identity purged, contributions survive
>   de-identified (the already-locked "remain, de-identified" design), the flow honest
>   about that trade. The **one sanctioned exception** to the append-only log: an
>   identity-scrub, legal not precedent.
>
> **Synchronous communal — LOCKED (2026-07-11).** We've designed the **async** communal layer
> exhaustively (shared notes, recognition, discovery, join-propagation, invitations); this is
> the **live** side. Launch = the cheap, warm slice only: **ambient co-presence** ("3 classmates
> studying Alkenes right now") — rides existing WebSocket presence, the synchronous twin of the
> recognition loop (aggregate, seen-not-surveilled) — **+ coordination** ("someone's building a
> test, want in?"), already the *second mode of the proximity check*, not a new system.
> **Deferred 🔮:** live study rooms / real-time competitive quizzing — heavy, and it flirts with
> the comparison/leaderboard anxiety we ruled out, so if ever, a separate opt-in game mode.
9. **Notifications** 🟡 — the delivery channel for 6/7/8 **and** spacing nudges
   ("5 days since you reviewed X"). *Aim:* preferences + **digest/batching** so it's
   signal not spam; **aggregate + anonymous for passive consumption** (reads),
   warmer and specific for active (took *your* quiz) — seen, not surveilled.
   The habit model this pillar serves is locked below.

> **The notification / habit model — LOCKED (2026-07-10).** The bet: build a Duolingo-grade
> return habit **without streaks**, because a streak is a *fake* loss (the number is
> arbitrary; doing today's lesson doesn't prove you learned) and streak-guilt is a dark
> pattern a learning product can't wear. The honest substitute is already in the substrate:
>
> - **Honest loss aversion via the forgetting curve.** The primary habit loop is the
>   **decay nudge** — FSRS decay (`ConceptState.due` / `stability`) *is* the loss clock, so
>   the thing slipping away is a real memory of a real concept and the action we ask for
>   (retrieval) is exactly what prevents the loss. Same lever the video credits for
>   Duolingo's 40% churn drop, pointed at something true. No streak counter needed — the
>   stakes are in §10, already computed.
> - **Recognition is the warm second loop** (§7): "someone took your quiz / used your note."
>   Social push, not the spine.
> - **Two tiers, not a blanket specificity rule.** *Weight-bearing* nudges (decay/habit —
>   they ask you to come back and work) **earn concept-level specificity** ("good time to
>   revisit the Krebs cycle," never "time to study" — the Google-Photos "specific thing, not
>   generic category" move). *Quick-info* (note finished synthesizing, N classmates joined a
>   course) stays **light** — no precision required.
> - **Voice is mild and warm, never guilt-threat.** Loss aversion is the *mechanism*; warmth
>   is the *register*. The honest stake sits *underneath* a gentle line, not waved in your
>   face — balanced against the kudos/recognition tone, never anxiety-farming (the video's own
>   study: killing notifications made people anxious and lonely — we don't become that).
> - **Rarity is the lever that lets us be mild.** Duolingo hammers daily, so it *needs* the
>   streak-threat to cut its own noise. We send **rarely**, so each notification carries weight
>   by scarcity alone and a soft, specific nudge actually lands. Low frequency + mild tone +
>   specificity-when-it-matters are mutually reinforcing — you can't keep the gentle voice
>   without the rarity.
> - **Decay nudges batch into a study-time digest.** Not a ping the moment each concept comes
>   due (frequent, naggy) — the system collects "here's what's slipping" and surfaces it
>   **once**, as one small warm "here's what's worth 5 minutes today," fired at the
>   **time-of-day the session log says you actually study** (the 15-min-gap session clustering
>   from the recap work, reused: it already knows when you show up — Duolingo's "23.5h after
>   last session," derived not configured).
> - **Out of bounds** (written out on purpose): streaks, manufactured scarcity, FOMO threats,
>   any framing that farms anxiety to earn a tap.
> - **Deferred threat, noted not solved:** OS-level AI (Apple/Google) now summarizes
>   notifications on-device and can flatten a crafted specific nudge back into generic mush —
>   a real future risk to the specificity tier, but an ecosystem trend, not a pre-launch build.
>
> **Blocked on:** §11 attribution (recognition) + §4 learning-science layer (decay clock as a
> queryable schedule). Design is settled; this is the spec to build against when those land.

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
13. **Offline + sync** ⬜ *(pulled into launch scope 2026-07-11 — was 🔮)* — design the
    retrieval substrate sync-friendly so we don't repaint later. Model locked below.

> **Offline / sync — LOCKED (2026-07-11).** **Existential for the market**, not a nicety —
> Nigeria/global-south connectivity, data cost, power gaps; students study in dead zones
> (library, transit, class, rural home). Offline not optional here (uLesson shipped offline via
> SD cards for the same reason). Also the endgame of perceived speed (local reads = 0ms).
>
> - **Offline-ready by construction.** The hard part of offline (write conflicts) is *mostly
>   absent by design*: attempts are **append-only** (union-mergeable, no conflict); the shared
>   note is **server-authoritative** (client caches, never edits → pull-only); **`ConceptState`
>   is derivable from the append-only log** (event-sourced — sync the events, re-derive state).
> - **Scope = reads + objective retrieval (decision B).** *Works offline:* all reads (note, key
>   points, concepts, downloaded audio); **objective retrieval** — pre-generated MCQ/pretest
>   banks are local, FSRS is local math, self-graded STEM worked-examples are local; resulting
>   attempts **queue as append-only events, union-merge on reconnect**. *Online-only:* capture
>   (needs server processing), AI-graded modes (ramble/teach), voice. Chosen over pure read-only
>   because (a) append-only already makes writes conflict-free so read-only's justification
>   dissolves, and (b) read-only offline would limit the dead-zone student to *reading* — the
>   fluency-illusion activity — while blocking *retrieval*, the real thing, contradicting the
>   core thesis.
> - **Sync mechanism (invalidation-based).** On app-open the client sends one `last_synced_at`
>   → backend returns **IDs changed since** (delta, not a full-list diff); client marks those
>   stale, serves local copies instantly otherwise, **fetches on navigate** to a stale item.
>   **Background-prefetch the likely-next** (current course, recent topic) right after
>   invalidation so navigation is already fresh. **Sync at boundaries** (app open, foreground
>   return) **+ a 10–15 min poll** — *not* per-navigation (data/latency). Mid-session changes
>   (a classmate's upload) ride the poll — not urgent. Plus an **append-only write-queue push**
>   on reconnect for the queued attempts. **AI online-only; Listen audio = explicit download**,
>   not auto-cache.
> - **Ownership:** native-first (local store + background sync — aligns with the v2 native
>   client). **Backend now:** ship sync-shaped endpoints (bulk course pull, delta invalidation,
>   append-only event push) so we don't repaint. *Still to nail: the exact endpoint contract +
>   on-device store schema.*

## First-run / onboarding (LOCKED 2026-07-11)

> **Note:** `docs/onboarding-designer.md` / `onboarding-marketer.md` describe the **v1** app
> (semester containers, "join a classmate's semester," a **streak**, a feature-by-feature
> screen tour) — **stale against v2** (emergent set, no containers, no streaks). Treat as
> historical; they need a rewrite. This section is the v2 shape.

- **Drive to first *retrieval*, not first upload.** Upload is setup, not the aha. The aha is
  the **honest catch** — being shown you don't know what you thought you knew. So activation =
  **"completed first retrieval,"** the metric onboarding optimizes (not "uploaded").
- **Gap-first, not gift-first — lead with the pretest.** After the first upload, *don't hand
  over the note yet*: "before you read anything, let's see what you already know" → they miss
  one or two → *then* the note appears to fill the gap. Delivers the whole "helps you, doesn't
  lie" prop in minute one and stamps the identity — a tutor who sees through you, not a
  summarizer. (Reuses the built pretest mode.)
- **Do the thing, don't tour it.** One guided path through a single real loop
  (upload → pretest → note → nail it) — not a chrome walkthrough. Same kill-the-choice
  philosophy as the daily entry point.
- **Hybrid to mask the processing wait.** A pre-loaded **demo topic** gives instant magic
  *while their own upload processes* in the background (OCR→chunk→embed→synthesize is
  seconds-to-minutes). Stack with **streaming synthesis** (the note writes itself) +
  **progressive reveal** (key points first, note after).
- **Plant the seeds that can't bloom yet.** Communal + longitudinal value doesn't exist in
  session one for a solo newcomer, so *promise* it honestly: contact discovery ("Ada from your
  school is on Organic Chem"); "we'll nudge you right before this fades" (sets up the decay
  return loop day one). **Minimal signal collection** — school/program to seed the emergent
  set, kept optional (a US first-year can't name a major; don't gate on it).

## Cross-cutting

- **Subject-awareness** — not a feature, a *knob on the engine*. Content-heavy
  (history, journalism) favours why-questions + ramble + teach; STEM favours pretest
  + applied problems + worked-example-then-vary; language favours output (ramble,
  production). Same engine, different mode mix (Part 12). STEM + subject-family model
  locked below.

> **STEM parity & subject families — LOCKED (2026-07-11).**
>
> **STEM is a parallel track through the whole pipeline, not a mode.** Content is visual/
> symbolic, so the gap is *born in capture* (preserve visuals — see §1). The **note** must
> render math (KaTeX/MathJax, not text) and keep worked examples/derivations *intact* (the
> steps are the content). **Retrieval** diverges hardest: you learn STEM by *solving problems*,
> not explaining — so the STEM mode family is **applied-problem** + **worked-example-then-vary**.
>
> *Build split (2026-07-17): **B9** shipped STEM retrieval (worked-problem + self-grade);
> **B10** queued for the two front surfaces a STEM student hits first — subject-aware **note**
> synthesis and **tutor**. Both are launch scope, not deferred: doing them before the native
> client means the designer builds a note/chat that hold math natively rather than retrofitting a
> prose-shaped UI (which is why the note + tutor shapes are now written into system-spec §4/§7).
> **Form follows content, and the family is a *prior* not a gate (owner call 2026-07-17):** one
> content-driven synthesis prompt renders math/worked-examples where the material has them and
> prose where it doesn't — on any topic — so a humanities note with a stray calculation renders it,
> a prose-only STEM topic stays prose, and a misclassified topic degrades gracefully instead of
> flipping the whole note's shape. The family only leans the default + drives the render hint;
> every note surface stays math-capable. What genuinely stays deferred is only **automated method
> grading** (SymPy/symbolic equivalence).*
>
> - **The grading wall + the launch dodge.** Rigorous automated STEM grading (method vs. answer,
>   partial credit, multiple valid methods, symbolic equivalence, units) is research-grade — it
>   needs tools beyond an LLM (SymPy for equivalence, code-exec for numerics). **Don't block
>   launch on it.** Launch STEM = **self-graded worked-example + calibration**: give problem →
>   solve on paper → *predict confidence* → reveal full worked solution → **self-grade**.
>   Sidesteps automated grading, still delivers the worked-example effect, and the existing
>   calibration mechanic fits perfectly. Hybrid method-grading (LLM + SymPy/code-exec) is a
>   deliberate **post-launch upgrade, not a blocker.** *(Queued as **B9**, 2026-07-17 — this
>   flow fell between B4's taxonomy scope and the queue; B4 declared `self_calibration`
>   without implementing it. B8's photo path is how the paper step arrives.)*
> - **Substrate wrinkle:** STEM "concepts" are often **procedures/skills** ("differentiate a
>   composite function"), not term↔definition — likely stretches the `Concept` model; accept as
>   a substrate change when the STEM modes get built.
>
> **The bigger frame — subject *families*, each a *profile*.** Not humanities-vs-STEM binary.
> A handful of families (content-heavy · STEM · **language** · more later), each a **profile
> bundling {rendering + mode-mix + grading}**. Language is genuinely distinct from STEM —
> non-Latin/RTL script rendering, production/comprehension modes (vocab SRS — FSRS fits vocab
> perfectly — conjugation, translation, **pronunciation/voice-central**), production grading.
> **Build subject-awareness as a profile abstraction, not `if subject == STEM` branches** — same
> "plugin, not rebuild" philosophy as the modes; a new family is a new profile. `subject_weight`
> was the first hint of this; it's really a profile selector. **Scope:** build STEM's profile now
> (launch), language is a recognized family for **later** — but designing the profile abstraction
> right now makes language additive, not a repaint. Don't build language yet; make the
> abstraction able to hold it.
>
> **The controlled taxonomy — LOCKED (2026-07-11).** The pass-2 `subject_weight` is a **loose
> placeholder** — `subject_type` is an *unbound free string with no producer* (nothing computes or
> stores it; the client passes a hint), and each mode ad-hoc string-matches inconsistent lists
> ("stem"/"science"/"math"/"engineering" = one family typed four ways). Replace it with:
> - **A closed enum — `SubjectFamily = STEM · LANGUAGE · HUMANITIES · GENERAL(default)`.** Coarse
>   on purpose (families = profiles); unknown → GENERAL; extensible later as new profiles.
> - **A real producer:** infer the family **once at synthesis** (the system already reads the
>   material — one cheap classification), **store `subject_family` on the Topic**, user-overridable;
>   concepts inherit their topic's family. *That* is "where it comes from / how it's computed."
> - **Centralize the mix:** one `family → {mode weights, rendering, grading}` **profile map** — the
>   `SubjectProfile` itself. Modes stop knowing about subjects; the profile owns the affinity
>   (exhaustive over the enum — no silent typo-misses). This is launch-plan **B4**.
- **Voice substrate** — shared by every voice mode; optimizing it lifts all of them.
  Full architecture in "Speed & voice" below.

## Speed & voice architecture (LOCKED 2026-07-11)

For voice, **latency *is* the product** — the "alive, digging-deeper" feel dies on lag,
not on bad prompts. Speed is a feature here, not polish. Three grounded facts today, each
a lever: (a) **`call_llm` is fully blocking** — no streaming anywhere, every surface waits
for the last token before showing the first; (b) **voice is batch-queue only**
(`grading_worker`: upload → enqueue → transcribe-whole-file → grade → notify-when-test-done)
— correct for batch, incapable of conversation; (c) **model routing is coarse** (openai
`gpt-4o-mini` vs deepseek, everything heavy on the mini, no fast-small tier, no heavy tier).

The moves:

- **Streaming is the universal primitive — build once.** Add `call_llm_stream()` beside
  `call_llm` (same router, `stream:true`, async generator). Every text surface inherits
  instant first-paint: tutor types like a person, the **note writes itself on screen** as
  it synthesizes, quiz/feedback stream. Cheapest, highest-impact, do first.
- **Two voice pipelines, not one.** *Keep* the batch lane (lecture transcription, Listen
  audio-lesson gen, grading a submitted test). *Build* a real-time lane for conversational
  ramble/teach: a persistent WebSocket session with **streaming STT + streaming LLM +
  streaming TTS, overlapped not summed** (STT runs while you talk; TTS starts on the LLM's
  first sentence), **VAD endpointing** (no "press done" button), and **barge-in** (cut it
  off mid-sentence). Trying to make one pipeline serve both is the trap.
- **Hybrid over speech-to-speech (the build-vs-buy fork).** Pure Realtime APIs (OpenAI
  Realtime / Gemini Live) are fastest but *hide the transcript* — and we grade the concept,
  which needs the words. So: streaming STT (transcript → grade) → streaming LLM → streaming
  TTS. Elegant core: **the same streaming LLM turn both speaks the Socratic follow-up and
  emits the structured grade** — one call, no extra round-trip; the grade is recorded
  off-turn so it never adds latency.
- **Work-ahead — hidden latency is free.** Pre-generate the **question bank per concept**
  (serving a question becomes a DB read — instant *and* cheaper); prefetch challenge N+1
  while answering N; pre-gen the quiz while they read the note; warm the voice socket on
  entry (zero cold-start on the first turn).
- **Model tiering done right.** Fast/cheap tier (Haiku/deepseek/mini) for high-frequency
  light turns (grade a one-liner, gen a question, ramble follow-ups); heavy tier (frontier)
  for the rare hard jobs (synthesis, applied-STEM grading, fact-check). The task→provider
  map exists; it just needs a real fast tier + sharper routing.
- **Perceived speed is a design stance.** First-*token* budget not total-time budget
  (nothing spins >400ms — it streams or it's optimistic); optimistic UI reconciled after;
  meaningful skeletons. **Offline/local-first (coming) is the endgame of this** — device
  reads are 0ms.

**Latency budget (defend these):** voice turn (you stop → it speaks) **< 800ms** overlapped ·
text stream first token **< 400ms** · action ack **< 100ms** (optimistic) · note first-paint
**< 1s** streamed. A voice turn crossing ~1s consistently stops feeling like conversation.

**Phasing:** (1) `call_llm_stream` + wire text surfaces — small, do first · (2) model tiering
— small, double-pays · (3) work-ahead / question-bank pre-gen — medium · (4) real-time voice
lane — the big new subsystem, gated as **premium** (feel + business align).

**Through-line — speed work double-pays.** The streaming / tiering / work-ahead / pre-gen
moves that make it *fast* are the *same* moves that make it *cheap* (see the cost notes and
Access model). Performance here is leverage, not a tax.

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

## Access & payment model (LOCKED shape, prices TBD — 2026-07-10)

The *shape* is decided; the *numbers* wait for real cost + behaviour data.

- **Fully paid, no freemium.** You subscribe to NotesOS as a whole — there is **no
  per-feature gate and no crippled free tier.** Either you're in or you're not.
- **Free at launch, priced later.** Ships free for an opening window to watch actual
  cost-to-serve and user behaviour *before* a price is set. You can't price a margin you
  haven't measured — and retrieval (per-seat, non-amortizing) is the dominant cost, so
  the number can only come from data.
- **Sharded / scale pricing — retired.** The old "more people in your class → cheaper
  per head" idea only held when NotesOS was a *pure shared-resource read product* (cost
  amortized across readers). Once retrieval became the center of gravity — **per-seat,
  doesn't amortize** — more users means more grading, not cheaper seats. The premise is
  gone with the per-class design.
- **Gift / sponsor a connection.** You can pay for (gift) a subscription for someone in
  your connection graph. This is the **humane valve for a hard paywall** — no free tier,
  but your study group can sponsor a classmate in, which keeps the paywall clean while
  staying communal. It doubles as a growth mechanic (the person you most want in the
  shared note is the one you'll cover). *Open, parked with pricing:* full transfer vs.
  time-boxed (month/term), and whose card renews.

## Deferred idea log

- **Video embed** — backend fetches/selects 1–2 YouTube links for a topic, note
  embeds them. Simple version only. Low-lift when we get to it.
- **Speech-emotion signal** — read hesitation/confidence from voice as extra
  calibration data. Interesting, overreach-prone, later.
