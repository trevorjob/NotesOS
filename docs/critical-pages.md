# NotesOS v2 — Critical Pages (build priority + states to create)

> **What this is.** [`page-spec.md`](./page-spec.md) lists *every* page. This file pulls out the
> **critical** ones — what to build first, and for each, the **distinct views + states** that must be
> created so none get forgotten. This is **build scope and priority, not design** — the look and layout
> are Claude Design's; this says *which pages, and which states of each, have to exist.*
>
> **Tiers are a proposed order — adjust freely.** Tier 1 is the launch-blocking core loop (nothing
> works without it); lower tiers complete the experience.

---

## Tier 1 — Critical (the core loop — build first; launch-blocking)

- **Register / Verify / Login** — get in. *States:* phone entry · code sent · code entry · resend /
  cooldown · expired · error · success · Google path (still verifies a phone).
- **Home / doorway** — land on the one thing to study. *States/views:* the one action (+ reason +
  time) · nothing-due (caught up → get-ahead offer) · **no concepts yet** (→ route to Capture) ·
  returning-with-fading.
- **Capture** — get material in. *Views:* input (files · photo · audio · text · syllabus) · processing
  · **proposed topic structure** (amendable) · confirm. *States:* per-item progress · partial / failed
  item · "Unsorted" fallback.
- **Note canvas** — read the note, mastery-lit. *States:* empty · **synthesizing** (writes itself) ·
  ready · updated (what changed / who added). *Also must hold:* mastery lighting on concepts ·
  in-place "test this concept" · "read the original" · "says who?" · "N built this."
- **Retrieval run** — the practice. *Mode views:* quiz (mcq · short-answer) · pretest · ramble · teach
  · recap · brain dump. *Overlays (not separate pages):* STEM worked (solve → predict → reveal →
  self-grade) · photo answer (snap → confirm → submit). *Flow states:* prompt · confidence-asked **vs**
  just-answer · answering (typed · spoken · photo) · grading · result (outcome + updated state +
  calibration).
- **Progress** — see your knowledge state. *Views:* the note lit by mastery (the spatial surface) ·
  optional summary glimpse · calibration when relevant · empty (no history yet).

## Tier 2 — Important (completes a real launch)

- **Onboarding** — gap pretest + demo-while-processing. *States:* welcome · capture-or-sample ·
  processing-wait (filled) · first pretest · first result.
- **Course list** — courses grouped by term. *States:* populated · empty.
- **Topic view** — topics + resources; jump to note; live presence. *States:* populated · empty · active-users.
- **Create course** — with the "did you mean this?" offer. *States:* form · matches offered (join /
  make-my-own) · created.
- **Join by invite** — code entry. *States:* input · invalid · joined.
- **Test builder + Take a test (C9)** — build a shareable graded test; take it. *Views:* scope pick
  (course / multi-topic) · count · type · **generating (progress)** · saved · the class's shared-test
  list · take (reuses the run surface) · derived result.
- **AI tutor chat** — ask, grounded in your materials. *States:* empty · question → streaming answer ·
  topic-scoped vs course-wide · error.
- **Settings** — persona (tone/emoji/style) · profile (school/program/year/phone) · sign out ·
  **delete account** (re-auth confirmed).
- **Notifications** — what's fading · a classmate added · recognition. *States:* list (read/unread) · empty.

## Tier 3 — Secondary (can follow launch)

- **Listen — audio lessons** — player over rotating TTS takes. *States:* generating · ready ·
  downloaded/offline · error.
- **Source reader** — the raw material behind the note. *States:* readable · empty · quarantined (uploader-only).
- **Discovery** — classmates + their courses. *States:* populated · empty (activity-gated).
- **Term filing** — create/manage terms, file courses.
- **Report / block** — flag content · block a user. *States:* report form · submitted · block confirm.

## Tier 4 — Ships later / behind a flag

- **Voice study** — real-time spoken study. *States:* listening · thinking · speaking · interrupted ·
  done · permission / error. (Ships dark — `ENABLE_VOICE_LANE=false`.)

---

## Not their own pages (build as overlays / states, not screens)
- **STEM worked problem** and **photo answer** — variants *inside* the Retrieval run, not separate pages.
- **"read the original" / "says who?" / "what changed" / "N built this"** — affordances *on* the Note
  canvas (source reader is the one that lands on its own view).
- **Cross-cutting states** (empty · synthesizing · updated · offline/sync · quarantined · error) —
  every page owes the relevant ones; they're states, not pages (system-spec §12).
