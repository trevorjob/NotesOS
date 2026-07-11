# NotesOS — System Behaviour Spec

> **For the person designing the native client.** This is **not** a brief telling you what to
> build or how it should look — you own the surface. This is **how the system underneath
> behaves**: what exists, what it expects from the user, what it produces, what happens when,
> what's instant vs. slow, what's live vs. cached, and what the system decides on its own vs.
> what it asks the user. Design *against* this and your screens plug straight into a backend
> that already works a certain way.
>
> The *why* behind every decision lives in [`product-map.md`](./product-map.md) and
> [`NotesOS_Architecture_NextPhase.md`](../NotesOS_Architecture_NextPhase.md). The **entire
> visual / aesthetic language is yours** — this doc deliberately says nothing about how anything
> *looks*, only how it *behaves*.
>
> Last updated: 2026-07-11.

---

## 0. Two principles that shape every screen

1. **Studying is hard; everything else is dead simple.** Retrieval *should* feel effortful (that
   effort is the learning). Every *other* act — getting notes in, finding the next thing to do,
   coming back — should have as little friction as possible. When in doubt, remove a choice.
2. **Helps you, doesn't lie to you.** The product exists to defeat the *fluency illusion* —
   feeling like you've learned without having. So the system will sometimes deliberately withhold
   comfort (show you a gap, tell you your confidence was wrong). Designs should frame that as
   honesty and care, never as failure.

---

## 1. The mental model

The universal spine is **School → Course → Topic → Resources**.

- **Course** — the only thing a user actively *joins*. It's the unit classmates share. Reached
  three ways: create it, discover it (a classmate is in it), or an invite.
- **Topic** — the atomic *learning* unit. **Everything a student studies lives at the topic
  level**: the consolidated note, concepts, quizzes, audio, chat, progress. When you design "a
  place to study," it's a topic.
- **Resource** — an uploaded thing (PDF, image, doc, audio) that feeds a topic.
- **Term / semester** — just a *label* that groups the courses you're taking in a period (for
  planning around exams). Not a container, has no members, born automatically with your first
  course. Use it to *organize the course list*, not as a level you navigate into.

**There is no "class" or "cohort" object.** Your classmates are simply *the people in your
courses* — computed live from shared enrollment. Where a school runs tight cohorts the same faces
recur across your courses (dense graph); where it's credit-based it stays loose. **One design
serves both** — don't build a "my cohort" screen; build "the people in this course" and let
density emerge.

---

## 2. Identity, access & invitations

- **Auth:** email/password + Google. Access tokens are short-lived (15 min) and refresh silently
  in the background — the user should essentially never see a session expire. Assume a logged-in
  session unless the refresh hard-fails.
- **No public/private, no roles, no approval, no moderators.** The only access control is the
  **invite link** — a valid link means you're in. There is nothing to "request access" to.
- **Two doors into a course:**
  - **Discovery (inbound, ambient):** the system *surfaces* courses your classmates are in. The
    user chooses to join. Never auto-joined. (See §9.)
  - **Invitation (outbound, deliberate):** you invite a **person**, not a course. Redeeming an
    invite lands them on the inviter's **roster** — the inviter's *current-term courses* — as a
    multi-select checklist ("here's what Trevor's taking; tick the ones that are yours"). Nothing
    auto-enrolls; they pick. This is what makes inviting a whole cohort one action instead of
    ninety.
  - There's also a **per-course invite code** for the surgical "join *this one* course" case.
- **Logged-out invite redemption** flows through signup and lands on the same picker — the invite
  link is the product's main front door, so that path must feel first-class, not an afterthought.
- **Gift / sponsor:** a user can pay for someone in their connections. (Post-launch — launch is
  free — but worth knowing the model exists.)

---

## 3. Capture (getting material in)

**The rule: never block getting material *in* on organizing it.** Capture is instant and dumb;
organization is deferred and smart.

**What can be captured:** typed/pasted text, PDF, DOCX, images (photos of boards/slides/
handwriting — multiple photos group into one resource), and **audio/lecture recordings** (record
in-app or upload a file → transcribed → becomes notes).

**The flow (this is the important part):**
1. User creates a **course** (one deliberate act — it's the join unit). This is the *only* manual
   organizing step.
2. *(Optional, powerful)* User adds the **course outline / syllabus** (paste or snap a photo). The
   system creates the semester's **topics as an empty scaffold** up front — so the whole course's
   shape is visible immediately, each topic a labeled bucket waiting to be filled.
3. User **dumps everything at once** — a whole folder, 40 photos, a semester of PDFs — in one
   action. **No *forced* per-topic filing.**
4. The system **sorts the pile into topics**:
   - *If an outline exists:* it **classifies** each file into the known topics (reliable — it's
     matching to labeled buckets).
   - *If not:* it **clusters** the pile and **proposes** a topic breakdown with names.
5. User sees the proposed structure and **confirms or tweaks** (drag a file, merge, rename). This
   is **review-and-adjust (opt-out)**, never file-it-yourself — the default is usually right, so
   most users just tap accept.

**Two entry points — destination is implied by *where* you "add" from.** The flow above is the
**course-level bulk** path (unsorted pile → auto-organize → confirm). There is also a **direct
path**: from *inside* a topic, "add" drops material **straight into that topic** — no
classification, no confirm. Navigating to a topic already implies the destination, so the system
honors it. The rule is *never force filing*, not *forbid* it. (A direct-add that clearly doesn't
belong gets a **gentle flag** — a suggestion, never a block.)

**Processing is asynchronous.** Upload returns immediately; OCR → chunking → embeddings →
synthesis happen in the background (seconds to minutes). So a resource moves through **states** the
UI must represent: `uploading → processing → ready` (and `failed`, `needs-review` for
low-confidence). The user keeps using the app while it works; **the system pushes a live event
when each resource finishes** (see §11), so screens can update without a manual refresh.

**Honesty seams the UI should surface:**
- **Low-confidence extraction** — a blurry scan is flagged ("hard to read — check it?"), not
  silently accepted as fact.
- **Quarantine** — a wildly off-topic upload is held out of the shared note automatically, and is
  **visible only to its uploader** (flagged), until later material corroborates it. So "your
  upload" can be in a *held* state that only you see.

**STEM/visual note:** figures, diagrams, and equations are **preserved and referenced**, not
flattened to text. Math renders as math. (Design needs to accommodate rendered formulas and
referenced figures inside notes.)

---

## 4. The Consolidated Note (the wedge)

**What it is:** one AI-synthesized document per topic that merges *everything everyone uploaded*
into a single authoritative study document — reconciling overlaps, merging complements. Plus **key
points** (exam-ready facts) and **concepts** (term ↔ definition, or for STEM, procedures). It is
meant to be *provably better than any single source* — the thing a student reads instead of their
scattered materials.

**Behaviour the design must reflect:**
- **It's a launch point, not a destination.** Reading it feels productive but *reading isn't
  studying* — so the note is wired to push the user into retrieval. It is the front end of the
  retrieval engine, not a read-only page.
- **Active surface.** The note is **linked to the concept substrate**: terms carry the user's
  personal **mastery state** (solid / fading / shaky), and the user can trigger a retrieval **on a
  concept or paragraph right there**, without leaving. Reading flows into testing.
- **It grows incrementally.** New uploads **merge into** the existing note (not a from-scratch
  rewrite). So the note has history: **"what changed since you last read"** and **"Ada added this
  section"** are real, surfaceable states.
- **Trust is quiet, never a debate.** The note always reads as **one authoritative voice** — it
  never shows "Source A vs. Source B disagree" inline. Two trust affordances only: a **"says who?"**
  tap that X-rays a single line's provenance *on demand* (for the skeptic), and a warm **"your
  cohort built this"** signal (real classmates, not a faceless AI). Corroboration happens silently
  during synthesis.
- **States:** a topic's note can be `empty` (no uploads yet — scaffold exists but no content),
  `synthesizing` (streaming into place — it visibly writes itself), `ready`, `updated` (changed
  since last view).

---

## 5. The Retrieval engine (the core loop)

Retrieval is **not "quizzes."** It's a set of **modes** over one per-concept substrate. The engine
measures **concepts**; the user consumes **topics**.

**Modes (how recall is triggered):**
| Mode | User does | Notes for design |
|---|---|---|
| **Quiz** | Answers structured questions | MCQ / short-answer; text or voice |
| **Ramble** | Speaks/writes freely about a concept | Open prompt; voice-first shines |
| **Teach** | Explains the concept as if teaching | Scored on correctness first |
| **Pretest** | Answers *before* studying | Expected to miss — it primes learning + feeds calibration |
| **Recap** | Free-recalls the *last session* | One response graded across many concepts |

**The moment-to-moment loop — the signature interaction (design this carefully):**
1. **Challenge** — the mode poses something.
2. **Predict confidence** — *before* revealing the answer, the user says how sure they are.
3. **Answer.**
4. **Reveal + calibration** — the user sees if they were right **and** how their confidence
   compared: *"you were 90% sure, you got it — calibrated"* / *"90% sure, but missed — you're
   overconfident here."* This calibration beat is the product's personality; it's honesty made
   interactive. **It should feel gentle and revealing, not punishing.**

**A session** is a *bout of retrieval* — the app clusters attempts into a session automatically
(a ≥15-minute idle gap ends one). No "start/stop session" ceremony required; it's derived. A
session should **end with a warm close** ("you firmed up 4 concepts; X is still shaky; recap
tomorrow?") — which is also the hook back.

**Difficulty is a feature.** Retrieval *should* feel hard; when something's hard and you get it,
that's when it sticks. The UI should frame hardness as the mechanism working ("that was hard —
which is why it stuck"), never as the app being broken.

**Adaptivity:** a session isn't a fixed 10-question form. The engine knows what's *due* (fading) and
can interleave modes and adjust — design for a responsive flow, not a rigid quiz.

**Scheduling:** every attempt advances a spaced-repetition schedule (FSRS). Each concept has a
**due** time; the system always knows what's slipping. This powers the home card and notifications.

---

## 6. Progress (without streaks)

**No streaks. No leaderboards.** Progress is honest, personal, and continuous.

- **Headline = living knowledge state.** Concepts are solid / fading / shaky and move in real time
  (with study, and with the passage of time). Unlike a streak, it's **continuous and forgiving** —
  things fade *gradually*, any retrieval revives them, nothing ever "breaks." Frame it as *tending*,
  not *protecting a fragile chain*.
- **Progress is spatial, not a scoreboard.** The primary way a user sees progress is **their notes
  lit by mastery** (solid terms glow, fading dim or something like that)**(honestly you can do what you want here - the system just provides a way to make you see the things you know and what you dont)** — you see your knowledge *across your own
  notes*. A dedicated stats view is optional depth, never the headline.
- **Framing balances gain and loss** — lead with growth ("4 got more durable today"), whisper the
  fading ("3 slipping") — gentle, never anxiety-inducing.
- **Calibration is the signature-but-quiet metric** — "you're getting better at knowing what you
  actually know." Surface it when relevant, not in the user's face.

---

## 7. Listen mode & the AI tutor (the support surfaces)

These are **passive** surfaces (you consume). They stay **low-friction and get out of the way** —
the "make you work" pressure lives in the retrieval modes, not here.

- **Listen** — an auto-generated **audio lecture** of a topic (lecture style — *not* a two-host
  podcast). It's **passive reinforcement / spacing**, honestly not a substitute for retrieval; the
  lowest-friction surface (commute, walking). Details: **a few variations rotate** (so it doesn't
  go stale on repeat listens); **"active-listen" seams** can pause and ask the user to answer out
  loud (optional, off by default). Audio is an **explicit download**, not auto-cached.
- **AI tutor** — a chat that has read everything in the topic **and knows the user's mastery
  state**, so it pitches explanations to their level. It **just answers** — a fast explainer /
  lookup to unblock and get out of the way (it is *not* Socratic; retrieval lives elsewhere). It's
  reachable **from everywhere** (inside a note, after a wrong answer, mid-Listen) and carries the
  context of wherever it was opened. Its tone is **tunable via the personality settings**
  (encouraging / direct / humorous, explanation style, emoji) — this is the surface where the
  product's personality is expressed.

---

## 8. Notifications & the habit loop

**The product builds habits without streaks — through honest decay.** Notifications are **rare and
meaningful, warm and mild** — scarcity is what lets them be gentle.

- **Primary loop — the decay nudge.** The system knows what's fading and, at the time of day the
  user actually studies (learned from their session history), sends *one* warm, **specific**
  digest: "good time to firm up the Krebs cycle — 5 min." Batched, not a ping per due concept.
- **Secondary loop — recognition** (warm, social): "someone took your quiz / used your note."
- **Two tiers:** weight-bearing nudges (decay/habit — earn concept-level specificity) vs.
  quick-info (note finished, N classmates joined — light, no precision needed).
- **Out of bounds:** streaks, manufactured scarcity, FOMO, anything that farms anxiety.
- **Passive vs. active tone:** aggregate + anonymous for passive consumption ("3 classmates
  studied this"), warm + specific for active ("took *your* quiz"). Seen, not surveilled.

---

## 9. The communal layer

NotesOS's moat is being **communal**. Most of it is **ambient and aggregate by default**, warming
to specific on inspection.

- **Discovery feed** — "courses your classmates are taking," with a join affordance. A course only
  surfaces once it has **activity** (an upload or a second member) — *except* a course a **connection
  just created**, which surfaces immediately and prominently ("Ada started Organic Chem — join?").
- **Join propagation** — when classmates join a course, it surfaces to *their* connections,
  **aggregated by course** ("Organic Chem — N of your classmates joined"), getting stronger as N
  climbs. It stays an ambient feed item until **2** connected classmates are in, then it escalates
  to a prompt. Aggregate + anonymous (a count), names revealed on inspection.
- **Recognition** — the dynamic "your work was used" signal (see §8). Aggregate for passive reads,
  warm for active engagement.
- **Contribution visibility** — the static picture: "N classmates built this note." Social proof
  and gentle accountability — **without a leaderboard**.
- **Synchronous (light, at launch):** **co-presence** — "3 classmates studying this right now"
  (ambient, aggregate). And **coordination** — "someone's building a test on these topics, want
  in?" Live study rooms / competitive quizzing are deferred.

> **All of the above ride one substrate** (consume/activity events, aggregated and warmth-tuned).
> They differ only in how loud and how aggregated. Expect consistent "ambient count → specific on
> inspection" behaviour across all of them.

---

## 10. Offline & sync

**Offline is essential** (unreliable connectivity, data cost, power gaps in the core market).

**What works offline:**
- **All reads** — notes, key points, concepts, downloaded audio, your knowledge state.
- **Objective retrieval** — MCQ/pretest (questions are pre-generated and local), FSRS scheduling
  (local), self-graded STEM worked-examples. Attempts **queue locally** and sync on reconnect.

**Online-only (show a clear "needs connection" state):**
- Capture (needs server processing), AI-graded modes (ramble/teach), voice, the AI tutor.

**Sync behaviour (cache-first, invalidation-based):**
- On app open / foreground return, the client asks "what changed since `last_synced_at`?" and gets
  back **IDs to mark stale**. Fresh items serve **instantly from cache**; stale items **refetch on
  navigation**. The system **pre-fetches likely-next items** (current course, recent topic) in the
  background, so navigation usually finds fresh data already there.
- Sync happens **at boundaries + a 10–15 min background poll**, *not* on every tap. A classmate's
  mid-session upload isn't urgent — it arrives on the next poll, no interrupting loading state.
- **States to represent:** `fresh` (serve now), `stale` (refetch on open), `syncing`, `offline`,
  `queued` (a local attempt waiting to push). The user should rarely see a spinner — prefer
  instant-from-cache + quiet background refresh.

---

## 11. The real-time channel (what arrives unprompted)

The app holds a live connection (WebSocket) per course. Screens should **update in place** when
these arrive — no manual refresh:

- `processing_status` — a resource moved (processing / ready / failed).
- Note/knowledge updated — a topic's consolidated note was re-synthesized (someone contributed).
- `grading:complete` — an async grade finished.
- Presence — `active_users` / user joined / left (co-presence).
- Notifications — recognition, decay nudges, quick-info.

Design implication: **most data can change while the user is looking at it**, gently. Plan for
live-updating counts, "updated" badges, and content that can refresh under the user without
yanking their place.

---

## 12. Cross-cutting states & timing (a designer's cheat-sheet)

**Perceived speed is a design decision.** Nothing should spin for more than ~400ms — it should
**stream** or be **optimistic**.

| Interaction | Timing behaviour |
|---|---|
| AI text (tutor, synthesis, quiz, feedback) | **Streams token-by-token** — first words in <400ms; the note visibly writes itself |
| An action (join, add, mark done) | **Optimistic** — reads as done instantly, reconciles quietly |
| Voice turn (conversational) | Feels near-instant (<~800ms to first sound); barge-in allowed |
| Upload/capture | Returns instantly; processes in background with live status |
| Screen navigation | Instant from cache; refresh quietly if stale |

**Universal states to design for every content surface:** `empty` (never a dead end — always
offer a next action), `loading/streaming`, `processing` (async work in flight), `ready`,
`updated` (changed live), `stale/offline`, `error/needs-review`, `queued`.

**Accessibility (a behavioural constraint, not visual direction):** target WCAG AA; decorative
elements should be `aria-hidden`; respect `prefers-reduced-motion`.

---

## 13. What NOT to design for yet (deferred)

So you don't spend effort on things that aren't coming at launch: video embeds in notes; live study
rooms / competitive quizzing; automated STEM *method*-grading (self-graded worked-examples ship
first); the language subject profile; timing/sleep-aware delivery; gift/sponsor + any pricing/
paywall UI (**launch is entirely free**). These are real, later — not launch.

---

## 14. One-paragraph summary

A student creates a course, snaps their syllabus, and dumps a semester of messy notes in one go; the
system quietly sorts it into topics and synthesizes each into a single trustworthy note that grows as
classmates add to it. Studying means **retrieval**, not rereading — the app poses challenges, asks how
sure you are, then shows you the honest gap, and schedules each concept to resurface right before you'd
forget it. Progress is your notes lighting up with what you know, not a streak. It nudges you back
rarely, warmly, and specifically; it works on a bad connection; and it always feels alive because
your classmates are quietly present in everything you touch. **Studying is the only hard part — the
rest is dead simple.**
