# NotesOS v2 — Page Spec (the complete page list)

> **What this is.** The full inventory of pages the native client needs — each as a one-liner:
> *page → what it holds.* **Function only.** How each looks and lays out is Claude Design's call;
> this doc just makes sure **no page is missing.** It's the terse index; [`page-map.md`](./page-map.md)
> is the fuller per-screen contract (states, backing endpoints, constraints), and
> [`system-spec.md`](./system-spec.md) is the behaviour.
>
> **How it was built:** by walking one complete user journey end-to-end (below), so every capability
> the backend has gets a page. The walk surfaced pages the earlier docs missed — flagged **⚠ new**.

---

## The complete flow (the walk that makes the list complete)

A student, first time to power use:

1. **Arrives** → **registers** with a phone number, gets a **one-time code**, verifies it. (Or taps
   **Google** — still enters + verifies a phone.) Optionally names their **school / program / year**.
2. **First run** → a short **onboarding**: instead of a tour, a quick gap-finding question or two
   while their first uploaded material processes in the background.
3. **Drops in material** → **capture**: files, a photo of notes, an audio recording, or pasted text —
   or a whole syllabus. The app proposes a **topic structure**; they confirm or tweak it.
4. **Lands home** → the **doorway**: the single best thing to do right now ("3 concepts slipping in
   Thermodynamics — 5 min"), not a dashboard. From here they can also reach everything else quietly.
5. **Opens a course** → their **course list** (grouped by term), into a **course**, into a **topic**
   and its **resources**. Switching between topics/courses is fast and flat, never a drill-up.
6. **Reads the note** → the **note canvas**: their scattered material consolidated into one studiable
   note, structure-first, with terms **lit by mastery**. They can pull up **"read the original"** (the
   raw source), ask **"says who?"**, see **what changed** and **who added it**.
7. **Wants it explained** → opens the **AI tutor chat** on the topic and asks questions in their own
   words; answers are grounded in their materials. ⚠ *(no page in the docs today)*
8. **Studies hands-free** → **listens** to the topic's short audio lessons (several rotating takes) on
   a commute. ⚠ *(no page in the docs today)*
9. **Tests themselves** → the **retrieval run**: a **quiz**, or a **ramble** (say everything you know),
   or **teach it**, or a **recap** of last session, or a **brain dump** of the whole topic. STEM
   topics **solve on paper → predict → reveal → self-grade**. Answers can be **typed, spoken, or a
   photo of handwritten work**.
10. **Was tested before studying** → a **pretest** primes new material (a guess is fine).
11. **Preps for an exam** → the **test builder**: picks a course or topics, a count, a type, and
    generates a **shareable graded test** — takes it (reuses the run surface), and sees the **class's
    shared tests**.
12. **Checks how they're doing** → **progress**: their knowledge lit across their own notes; how well-
    calibrated they are, when it's relevant.
13. **Studies out loud** → the **voice** lane: a real-time spoken back-and-forth (ships later).
14. **Gets pulled back** → a **notification**: something's fading, or a classmate added to a shared
    note.
15. **Adjusts things** → **settings**: how the AI talks to them (tone/emoji/style), their profile,
    sign out, or delete their account. If something's wrong, **report or block**.

Every capability the backend has is now on the list. The ⚠ pages are the real gaps.

---

## The pages

### Auth & onboarding
- **Register** — phone number → send code; optional school / program / year.
- **Verify code** — enter the OTP; resend / cooldown.
- **Login** — returning user: phone + password.
- **Google sign-in** — one tap; a new account still enters + verifies a phone.
- **Onboarding** — first run: a gap-finding pretest + something useful to do while first content
  processes (not a tour).

### Home & capture
- **Home / doorway** — the one best thing to study now (+ why, + time); quiet access to everything else.
- **Capture** — drop files / photo / audio / text (or a syllabus); confirm the proposed topic structure.

### Courses, topics & people (the spine)
- **Course list** — your courses, grouped under terms.
- **Create course** — name it → see near-match "did you mean this?" offers → join one or make your own.
- **Join by invite** — enter a course code.
- **Discovery** — your classmates, and courses your classmates take that you're not in.
- **Term filing** — create/manage your terms; file courses under them.
- **Topic view** — a course's topics + resources; jump into the note; who's studying right now.

### Reading, tutor & audio
- **Note canvas** — the consolidated note; terms lit by mastery; tap a concept to test it right there;
  "read the original"; "says who?"; "what changed since you last read"; "N built this note."
- **Source reader** — the raw uploaded material behind the note ("read the original" opens this). ⚠ new
- **AI tutor chat** — ask anything about the topic/course in your own words; answers grounded in your
  materials (streams in). ⚠ new
- **Listen** — play the topic's short audio lessons (several rotating takes); hands-free / background. ⚠ new

### Testing & progress
- **Retrieval run** — the practice surface for every mode (quiz · pretest · ramble · teach · recap ·
  brain dump): a prompt → (predict confidence) → answer → result. Answer by typing, speaking, or a
  photo of paper work.
- **STEM worked problem** — solve on paper → predict → reveal the worked solution → self-grade.
- **Photo answer** — snap handwritten work → confirm the transcription → submit.
- **Test builder** — pick a course or topics → count → type → generate a shareable, graded test.
- **Take a test** — run an authored test (reuses the run surface); plus the list of the class's shared tests.
- **Progress** — your knowledge lit across your own notes; calibration surfaced when relevant.

### Voice
- **Voice study** — real-time spoken back-and-forth study on a concept.

### Account & system
- **Settings** — how the AI talks to you (tone / emoji / explanation style); your profile
  (school / program / year / phone); sign out; delete account.
- **Notifications** — what's fading, what a classmate added, recognition.
- **Report / block** — flag a resource / note / AI answer; block a user.

### Cross-cutting states (not pages — every relevant page needs them)
Empty · loading vs. *synthesizing* (the note writes itself) · updated · offline / syncing · quarantined
/ held · error.

---

## Gaps this walk found (now backfilled into page-map, 2026-07-25)
- **AI tutor chat** — the `study_agent` surface (ask questions, answers grounded in your materials,
  streams). Was missing; now a full page-map entry.
- **Listen** — the audio-lesson surface (`audio_generator` makes rotating TTS takes per topic). Was
  missing; now a full page-map entry.
- **Source reader** — "read the original" needed a real place to land; now a full page-map entry.

> **Build priority + the states each page needs:** [`critical-pages.md`](./critical-pages.md) pulls
> the critical pages out of this inventory and lists the views/states each must be built with.
