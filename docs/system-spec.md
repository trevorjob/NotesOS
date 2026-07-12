# NotesOS — System Behaviour Spec

> **For the person designing the native client.** This is **not** a brief telling you what to
> build or how it should look — you own the surface. This is **how the system underneath
> behaves**: what exists, what it expects from the user, what it produces, what happens when,
> what's instant vs. slow, what's live vs. cached, and what the system decides on its own vs.
> what it asks the user. Design *against* this and your screens plug straight into a backend
> that already works a certain way.
>
> The **entire
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
serves both** — there's no cohort *object* to represent; what's real is **"the people in this
course,"** and cohort density emerges from course overlap on its own.

---

## 2. Identity, access & invitations

- **Auth:** **the phone number is the primary identity** — the unique key *and* the login,
  verified by **OTP** (likely WhatsApp in the core market, where SMS is costly/flaky). This fits
  what NotesOS is (a communal tool whose social graph already runs on phone — see contact
  discovery, §9/§14) and its market (where phone *is* identity and phone-first signup is the norm,
  which also lowers invite-funnel friction). **Google sign-in stays** as a low-friction path, but
  it's a convenience *into* the account, not the identity — an OAuth signup still requires the user
  to **enter and OTP-verify a phone themselves.** The phone is **never inferred from Google** (that
  number may be stale) — the user types their current, main one, so we know it's really theirs. **Email is optional** (recovery + whatever sign-in provides); push (§8) does the
  notifying, so email is no longer load-bearing. Access tokens are short-lived (15 min) and refresh
  silently — the user should essentially never see a session expire.
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
   most of the time the user just accepts it.

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
  affordance that reveals a single line's provenance *on demand* (for the skeptic), and a warm **"your
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
2. **Predict confidence** *(optional, contextual — see below)* — *before* revealing the answer, the
   user says how sure they are.
3. **Answer.**
4. **Reveal (+ calibration if a prediction was given)** — the user sees if they were right; if they
   predicted, *also* how their confidence compared: *"90% sure, you got it — calibrated"* / *"90%
   sure, but missed — you're overconfident here."* The calibration beat is the product's
   personality; it's honesty made interactive. **Gentle and revealing, never punishing.**

> **The confidence beat is NOT compulsory.** Forcing "how sure are you?" on *every* attempt is
> friction that turns a signature moment into a nag. It's the **whole point of a pretest**, and
> valuable on **new / shaky** concepts and deliberate open-ended modes — but a **tax on rapid review
> of near-mastered concepts** and quick drills, where it breaks flow. Surface it **where it earns
> its place; let the user just answer everywhere else.** (Backend already supports this:
> `predicted_confidence` is optional, and calibration is only computed/shown when a prediction was
> given — so this is purely a *when-to-ask* design call, not a data requirement.)

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
**due** time; the system always knows what's slipping. This powers the home and notifications.

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
- Sync happens **at boundaries + a 10–15 min background poll**, *not* on every interaction. A classmate's
  mid-session upload isn't urgent — it arrives on the next poll, no interrupting loading state.
- **States to represent:** `fresh` (serve now), `stale` (refetch on open), `syncing`, `offline`,
  `queued` (a local attempt waiting to push). The user should rarely see a blocking wait — prefer
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

Design implication: **most data can change while the user is looking at it**, gently. Content should
be able to update and mark-itself-changed under the user, and counts should live-update — without
ever yanking their place or interrupting what they're doing.

---

## 12. Cross-cutting states & timing (a designer's cheat-sheet)

**Perceived speed is a behavioural target.** Nothing user-facing should present a *blocking* wait
longer than ~400ms — it should **stream** as it arrives or be **optimistic** (act done, reconcile
after).

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

## 14. Flows, screens & states the feature sections assume

The sections above describe each *feature's* behaviour. This one fills the **connective tissue** —
the screens and flows *between* them, and states that hadn't been named. Still behaviour, not
visual direction.

### 14.1 App shape & the home

- **The spine of navigation:** Home → your **Courses** (grouped by term) → a **Topic** (the study
  hub — note, key points, concepts, quizzes, Listen, chat all live here) → a **study session**. How
  that's expressed is entirely yours — the only fixed thing is the *graph* (what leads to what).
- **The home is a doorway, not a dashboard.** Its job is to **remove the "what should I study?"
  decision** — the moment where sessions die before they start. It surfaces the single
  highest-value thing to do right now (usually **review** what's fading) and makes starting it
  effortless. **New** material (a classmate uploaded, the note grew) is present but *secondary* — it
  must not displace review as what leads. **Never empty-handed** — if nothing's due there's still a
  next move (a pretest, getting ahead, fresh material). Opened *from a push nudge*, the user lands
  **straight in** the promised session, not back on home.
- **No global search / no public browse *exists*.** There's no "find any course in the world"
  capability — courses are reached only through the classmate graph (§9) and invitations (§2). The
  *only* search anywhere in the product is the **school typeahead at signup**. (A fact about what
  the system can do — not a design constraint.)

### 14.2 First-run is two different flows

- **Creator first-run:** create course → *(snap syllabus)* → **dump** material → **gap-first
  pretest** ("let's see what you know" *before* the note) → then the note. The aha is the **honest
  catch**, not the pretty summary. Activation = **completed first retrieval**, not "uploaded." A
  **demo topic** can give instant magic while their own upload processes.
- **Joiner first-run:** you join a classmate's course that **already has a note** — your first
  experience is **consuming a ready note**, not capturing. Warmer and instant; design for value on
  arrival. (A just-joined course may still be **processing** — show it building, don't show empty.)
- **Cold start (no courses yet):** contact discovery ("3 of your contacts are here") + a coarse set
  from school/program seed the graph. The home is **never a dead empty state** for a new user.

### 14.3 Inviting & the people around you (the sender side)

- **Invite a person:** generate a link and share it (however sharing works on the platform). The
  receiver side (roster picker) is §2. There's also **"share this course"** (the per-course code)
  for the single-course case.
- **People are per-course, not a global cohort.** "The people in this course" is a real surface; a
  **"my whole cohort" screen is not** (the set is emergent — §1). A person view stays minimal
  (shared courses). Everything else about classmates is ambient/aggregate (§9).

### 14.4 Instant vs. delayed feedback (this shapes the session screen)

The 3-beat loop (§5) isn't uniformly instant:
- **Objective retrieval** (MCQ, pretest, self-graded STEM) — graded **instantly / locally**, so the
  reveal + calibration are immediate. **Works offline.**
- **AI-graded** (ramble, teach, voice) — grading is a **server LLM call**: a short in-flow wait,
  ideally **streamed** ("scoring your answer…" → feedback streams in), *not* fire-and-forget.
  **Online-only.** Design a graceful brief-wait state for these; don't assume instant.

### 14.5 Voice interaction states

Voice (conversational ramble/teach) is a **live exchange, not record-then-submit**. States to
design: **mic-permission** (asked in context, first use) → `idle` → `listening` (user speaking) →
`thinking` → `speaking` (system responding) → `interrupted` (user barges in — it stops and listens)
→ `done`. A live transcript is optional. **Offline / no signal → a clear "voice needs a connection"
state** (voice is online-only).

### 14.6 Native permissions & push

- **Permissions are requested *in context*, never all upfront:** microphone (voice + lecture
  recording), camera (snapping notes/syllabus), contacts (contact discovery — optional, cold-start
  only), notifications (push). Each needs a graceful *denied* path (e.g. camera denied → still allow
  file upload).
- **Push notifications** carry the decay nudge / recognition to the OS. **Tapping one deep-links
  straight to the thing** (the exact session / note / course) — it must not dump the user on the
  home screen to re-find it.

### 14.7 Managing & deleting (and the consequences)

- **Leave a course:** your enrollment ends; **your past contributions stay** in the shared note (it's
  communal — leaving doesn't gut it).
- **Delete a resource:** allowed, but it **re-triggers synthesis** — the note re-merges *without* it,
  so the user sees a "note updating" consequence, not a silent removal.
- **Topics:** rename / merge / move resources between them (never required — §3).
- **Delete account:** signs out and removes the person. **Their contributions to shared notes
  remain, de-identified** — the communal note isn't destroyed when one person leaves. Not a hard
  cascade.

### 14.8 The notification inbox

Beyond OS push, there's an **in-app inbox**: notifications with **read/unread**, **digested/grouped**
(not a firehose), same tone rules as §8 (aggregate for passive, warm for active). Clearing/marking
read is a real interaction.

### 14.9 A few more states to have on hand

- **Empty scaffolded topic** — exists (from the outline) but has no material yet → offer "add material."
- **First-ever synthesis** — a brand-new note assembling for the first time (streams in; distinct
  from an *update* to an existing note).
- **Failed processing** — a resource failed OCR/transcription/synthesis → offer **retry or remove**.
- **Invite edge cases** — invalid link, or **"you're already in this course."**
- **School search no-results** → "type it in" (free entry, canonicalised).
- **Attempt didn't sync** — an offline-queued attempt still pending push (rare, but a state).

### 14.10 Contact discovery (the cold-start social seed)

- **Purpose:** turn phone contacts into a starting social surface so a **new user** (zero course
  overlap → empty classmate graph) isn't alone on day one — the bridge from *phone friend* →
  *coursemate*. Reliable now that phone is verified for everyone (§2).
- **Mechanism (privacy-sensitive):** opt-in contacts permission (**skippable** — the school/program
  seed still covers cold-start) → the client normalizes numbers to canonical form and **SHA-256
  hashes** them → sends **hashes only** (never raw numbers or names) → the server matches against
  its verified-users' hash index → returns matched user IDs + minimal profile → the client shows
  each by *your own* contact name. Non-matches are discarded; non-users are never stored.
- **Hard rules:** **never message or auto-invite non-user contacts** (no spam-your-address-book
  growth hack — it surfaces *only people already on NotesOS*); opt-in and transparent (numbers
  hashed, contacts not stored, nobody messaged).
- **Honest limits:** hashing is the pragmatic standard, not cryptographically strong (phone-number
  space is brute-forceable) — acceptable for launch. And it's **thin early, compounds later** — few
  contacts are on a small new app; value grows with the user base.
- **Ties it creates:** a discovered contact who's a user becomes a lightweight **connection** (feeds
  invitation targeting + "a connection created a course → it surfaces"), distinct from a
  **classmate** (shared course). Two tie sources: *classmates* (course overlap) · *connections*
  (contacts + people you've invited).

---

## 15. Data the system collects — inputs, fields & the values behind the screens

The behaviour sections above describe *flows*; this one is the **data** underneath them — what the
user submits, what's required vs. optional, and the fixed value-sets the UI renders. (Field *names*
are indicative, not the API contract — that's in the backend.)

### 15.1 Signup & profile (the emergent-set signals)

| Field | Required? | Notes |
|---|---|---|
| **Phone** | ✅ **(primary identity)** | the unique key **and** the login; **OTP-verified** (WhatsApp/SMS). Also powers **contact discovery** ("3 of your contacts are here") — now a reliable cold-start seed because everyone has one. |
| Name | ✅ | |
| **School** | ✅ | picked from a **curated list via typeahead search**, or typed in (the system canonicalises "Unilag"/"UNILAG"/"University of Lagos" to one). School is the top of the spine + the proximity hard-filter. |
| **Email** | ⬜ optional | recovery + whatever **Google sign-in** provides. *No longer the primary key* — push does the notifying. |
| Password | ⬜ optional | phone is OTP-verified and Google is an option, so a password isn't strictly required. |
| **Program / major** | ⬜ optional | a grouping + proximity-ranking signal. **Kept optional on purpose** — a US first-year often can't answer; blank is fine. |
| **Entry year / rough entry window** | ⬜ optional | ranking signal (weaker where cohorts are loose). |

> **Design implication:** signup is **phone-first** (number → OTP), with **Google sign-in** as a
> fast alternative that still collects a phone. Onboarding stays *minimal and skippable* past the
> required set (phone, name, school); the optional signals sharpen discovery but never gate it.
> (A password isn't required — phone is OTP-verified — so don't assume a password field is mandatory.)

### 15.2 Creating a course / term / topic

- **Course:** name (✅), course code (⬜ — *one hint, never the key*; codes disagree across
  schools), the **term** it's filed under, school (inherited). Creating a course **runs the
  proximity check** → see the flow below.
- **Term:** not free text — composed from **`division_type` + `division_value` + optional
  `study_level`** into one canonical label ("200 Level · Second Semester", "Year 1 · Term 2",
  "Fall Semester"). User-created, reusable, personal. The UI offers the controlled vocabulary; the
  label is computed.
- **Topic:** normally **auto-created** (outline scaffold or auto-organize, §3). Manual create/
  rename/merge is available but never *required*.

### 15.3 The proximity "did you mean this?" flow (an interactive input moment)

When a user creates a course, the system may find near-matches at their school and **offer them
instead of creating blindly**. It returns candidate courses each with a **member count** and the
**reasons it matched** (same program / entry year / shared classmates). The user then either
**joins an existing one** or **"make my own"** (forks deliberately). *The offer never forces a
merge* — "make my own" is always live. The same pattern reappears as coordination ("someone's
already building this test — want in?"). Design this as a first-class branch of creation, not an
error state.

### 15.4 Settings & preferences the user controls

- **AI personality** (tunes the tutor, §7): tone (**encouraging / direct / humorous**), explanation
  style (**concise / detailed / example-heavy**), emoji on/off.
- **Notifications:** preferences over which nudges to receive; the digest is on by default.
- **Profile / account:** edit name, change password, sign out, delete account.

### 15.5 What the user submits *during study*

- **A retrieval attempt:** the chosen **mode**, the **scope** (topic / course / concept), a
  **predicted-confidence** (before the reveal), and the **response** — typed text **or voice
  audio** (both are graded).
- **Test generation** (where offered): course, **topics (multi-select)**, number of questions,
  type (MCQ / short-answer / mixed), difficulty.

### 15.6 The fixed value-sets the UI renders

The screens display these system enums — design needs a treatment for each value:

| Thing | Values |
|---|---|
| Predicted confidence | a 0–1 value (the *form* it's captured in is entirely yours) |
| Grade (spaced-rep) | `again` · `hard` · `good` · `easy` |
| Calibration verdict | `underconfident` · `calibrated` · `overconfident` |
| Concept / knowledge state | `solid` · `fading` · `shaky` (+ a "due" time) |
| Answer status | `correct` · `partial` · `needs-review` |
| Resource state | `uploading` · `processing` · `ready` · `failed` · `needs-review` (low-confidence) · `quarantined` (uploader-only) |
| Sync state | `fresh` · `stale` · `syncing` · `offline` · `queued` |

### 15.7 Editable vs. system-owned, limits, and roles

- **System-owned (not user-editable):** the consolidated note, key points, concepts — they're
  *synthesized*. You influence them by **uploading**, never by editing the text.
- **User-manageable:** topics (rename / merge / move resources between), resources (add / delete /
  move), a course's name+term, your own terms, your settings. **Retrieval attempts are append-only**
  — history is never rewritten.
- **Accepted uploads:** text, PDF, DOC/DOCX, images (jpg/jpeg/png/webp/tiff/bmp), audio. Images are
  compressed (→ webp) on the way in; **per-file size and per-upload count limits apply** — there's a
  clear over-limit state to handle.
- **No roles, no admins, no permissions tiers.** Everyone in a course is equal; access is purely
  "holds a valid invite / is enrolled." There is nothing to administer, approve, or moderate — so
  no such surface exists to design.

---

## 16. One-paragraph summary

A student creates a course, snaps their syllabus, and dumps a semester of messy notes in one go; the
system quietly sorts it into topics and synthesizes each into a single trustworthy note that grows as
classmates add to it. Studying means **retrieval**, not rereading — the app poses challenges, asks how
sure you are, then shows you the honest gap, and schedules each concept to resurface right before you'd
forget it. Progress is your notes lighting up with what you know, not a streak. It nudges you back
rarely, warmly, and specifically; it works on a bad connection; and it always feels alive because
your classmates are quietly present in everything you touch. **Studying is the only hard part — the
rest is dead simple.**
