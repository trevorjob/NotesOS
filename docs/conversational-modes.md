# Conversational retrieval modes (teach · ramble) — design note

> **Status: design, not built (2026-07-30).** This is the escalate-first artifact for a change to
> the retrieval *mode boundary* — read before writing code, react before we build. It does not
> change the one-shot modes (quiz / pretest / worked) at all. Canonical retrieval architecture still
> wins on conflict; this extends it, it doesn't override it.

## 1. Scope — why only these two

Teach and ramble are the modes where **a single answer isn't the retrieval act — the back-and-forth
is.** Everything else stays one-shot:

- **Teach** (protégé): you explain the concept; the AI plays a confused classmate and probes the
  *gaps* — "wait, why does that follow?"
- **Ramble**: you free-dump what you know; the AI is a curious friend pulling the thread — "ok but
  why does it happen like that? then what? you said X earlier — why?" It's a **hybrid**: opens like a
  one-shot dump, but the AI digs when there's more in your head to surface.

Quiz, pretest, and worked never enter this loop.

## 2. The invariant that must not break

**One bout = one FSRS grade = one `ConceptState` write, committed once at close.** The conversation
is *scaffolding before that single commit* — it must not multiply attempts. Calibration
(predicted-vs-actual) is still captured once. `engine.record_attempt` stays the only writer of
`ConceptState`. If the dialogue produced N turns, it still produces exactly **one** graded attempt.

## 3. The rails — mode-contract extension

Today a mode is `generate() → Challenge` then `evaluate() → Outcome` (see
`services/retrieval/modes.py`). A conversational mode opts into an extended contract *alongside* the
one-shot one:

- `open(concept, ctx) → Challenge` — the opening ask.
- `turn(concept, history, user_msg, ctx) → TurnResult` — **either** the next probe **or** a
  `close(reason)` signal. The AI decides *dig vs close* every turn; that decision is the heart of the
  mode.
- `close(concept, history, ctx) → Outcome` — the single graded judgement over the whole transcript
  (score + grade + feedback), fed to `engine.record_attempt` exactly as a one-shot Outcome is.

`TurnResult` is a small union: `{ reply: str }` (keep going) or `{ closed: true, reason }` (done).

## 4. Close conditions — any one ends the bout

1. **AI judges it done** — thread exhausted (ramble) or explanation complete enough to grade (teach).
2. **User emptied out** — a thin or blank turn. Ramble gives **one** gentle nudge, then if still
   nothing, closes gracefully. *Don't badger a blank brain* — this is the line between a study
   partner and a quiz robot.
3. **User taps done** — always available; closes immediately.
4. **Turn cap — ~7 user turns (`MAX_CONVO_TURNS = 7`).** A hard ceiling: after 7 the AI accepts what
   it has and closes regardless of how juicy the thread is. Bounds cost, time, and the interrogation
   feeling. Tunable constant, not a magic number scattered around.

## 5. Teach vs ramble — same rails, different soul

| | **Teach** (protégé) | **Ramble** (curious digger) |
|---|---|---|
| AI persona | confused student — "I don't get *why*…" | interested friend pulling the thread |
| User posture | structured explanation | free dump; often stalls / goes blank |
| `turn` job | probe the *gaps* in the explanation | follow the live thread; surface more |
| Closes when | explanation complete enough to grade | well is dry (+ don't-badger rule) or cap |

They differ only in the **prompt driving `turn`**, the **persona**, and the **close heuristic** — the
rails, the invariant, and the grading commit are identical.

## 6. Grading over a transcript

The Outcome reflects **how much / how well they retrieved across the whole exchange**, not per turn.

- **Teach**: judge correctness / completeness / clarity of the full explanation (as
  `teach_mode._judge` does today, but over the dialogue, crediting what the probing pulled out).
- **Ramble**: judge the depth and accuracy of what was surfaced across the dig — a rich, thread-
  following dump grades higher than a thin one that stalled at turn 2.

Both map score → FSRS grade via `score_to_grade` (or a mode override), same as one-shot.

## 7. API surface (proposed — decision point in §10)

- **`/next`** still *opens*: returns `challenge_id`, the opening prompt, and a `conversational: true`
  marker so the client runs the turn loop instead of the single answer box.
- **`POST /retrieval/turn`** `{ challenge_id, message }` → `{ reply, closed, close_reason? }`. Server
  accumulates the transcript keyed by `challenge_id` and enforces `MAX_CONVO_TURNS`.
- **Grading commit** (settled): the **final `/turn`** (with `closed: true`) *returns the Outcome
  directly* — one commit, the client does nothing extra. Cleanest experience; the one-shot `/attempt`
  symmetry isn't worth an extra round-trip mid-conversation.

## 8. Transcript state

The running dialogue lives **server-side, ephemeral, keyed by `challenge_id`** — Redis with a
session TTL fits: it's scaffolding, not a record. Consistent with "sessions are derived, not stored."
Only the final **Outcome** persists (via the attempt); the raw turns are discarded after grading
(optionally keep a short AI-written summary for the feedback line — decide in §10). This keeps us from
accumulating a pile of half-conversations in the DB.

## 9. UI direction (exploratory — we're vibing, not locking)

The feel we're reaching for: it should read like a conversation, not a form.

- **Live transcript.** As you speak, your words appear on screen in real time (already supported —
  `interimResults` streams into the field). In a conversation this becomes a **chat-like stack**: AI
  turns and your turns interleaved, scrolling.
- **Push-to-talk, auto-advance (settled).** One big **Speak** button — hold-to-talk (release = send
  that turn) or tap-to-toggle. On release the turn **sends straight through** and the AI replies —
  **no confirm step**, like a real conversation. (This is the deliberate exception to the one-shot
  edit-before-grade rule: flow beats correction here, and a mis-heard turn just gets clarified in the
  next reply, same as talking to a person.)
- **TTS-out: server-side streaming, free (2026-07-30).** The AI's probes are read aloud via the
  **shared OpenAI-TTS provider**, **streamed** end to end — `GET /api/retrieval/tts?text=…` is a
  `StreamingResponse` proxying `audio_generator.stream_speech` (httpx `client.stream` → `aiter_bytes`),
  so playback can start before the clip finishes; played through `expo-audio`
  (`createAudioPlayer({uri, headers})`) with a mute toggle. *(First tried on-device `expo-speech`;
  user disliked the voice → swapped for the provider we already use for topic audio.)* Bounded to
  short text (≤400 chars) — not the async `audio_worker`/Cloudinary long-audio path. Courtesy layer:
  failure is swallowed, loop stays text-first. Not premium-gated.
- Notebook aesthetic throughout; respect `prefers-reduced-motion`; each spoken turn is short (well
  under the on-device STT ~1-min cap), so STT is a natural fit here.

## 10. Decisions (settled 2026-07-30)

1. **Grading commit shape** — ✅ final `/turn` returns the Outcome directly; one commit, no trailing
   `/attempt` call. (Best experience.)
2. **Predicted confidence / calibration** — ✅ captured at `open` (before you start talking — "how
   well do you think you know this?"), actual = the close score.
3. **Ingestion** — ✅ push-to-talk (hold or tap), **straight auto-advance, no confirm** — like a real
   conversation.
4. **Turn cap** — ✅ `MAX_CONVO_TURNS = 7`. It's just a graceful ceiling on the back-and-forth; the
   system wraps up cleanly when it's reached, no tuning ceremony needed.
5. **Transcript retention** — ✅ keep a short AI-written summary post-grade (for the feedback line +
   the recognition-loop contribution); the raw turn-by-turn is still discarded.

All settled — the note is build-ready. First implementation fork is the mode-boundary extension
(`open/turn/close`) + `POST /retrieval/turn`, behind the §2 invariant.

## 11. Build status

- ✅ **Backend rails (2026-07-30).** `modes.py` grew the conversational contract
  (`ConversationTurn` / `TurnResult` / `is_conversational` / `MAX_CONVO_TURNS = 7`); a shared
  `conversation.py` owns the dig-vs-close turn LLM (persona-parameterised, don't-badger baked in);
  `teach_mode` + `ramble_mode` are conversational (`open/turn/close`) while keeping one-shot
  `generate/evaluate` for `run_once`/offline/tests. `POST /retrieval/turn` drives the loop over an
  ephemeral Redis transcript; `/next` flags `conversational: true`; **one graded attempt at close**
  via `engine.record_attempt`, calibration off the confidence stamped on turn 1. Close fires on
  mode-done · `end` · the 7-turn cap. Tested: `test_conversational_modes.py` + `/turn` API tests
  (dig→close, one-attempt invariant, `end`, cap, one-shot-rejection, ownership). Full retrieval
  suite green (177).
- ✅ **Client seam.** `mobile/src/lib/retrieval.ts` — `NextChallenge.conversational`, `submitTurn`,
  `ConversationTurnResult`.
- ✅ **Mobile UI (2026-07-30).** The conversational bout ships in `mobile/src/`:
  `components/retrieval/ConversationalBout.tsx` (confidence-at-open → chat-transcript loop →
  graded close, keyed by `challenge_id`) and `usePushToTalk.ts` (live partial words, tap-to-toggle,
  auto-advance send-on-stop, chunk-restart across iOS's ~1-min cap). `retrieval.tsx` branches to it
  when `challenge.conversational` on a teach/ramble challenge; the one-shot open path is untouched.
  Shared result/confidence pieces extracted to `retrievalShared.tsx`. **No turn counter** (the cap
  is a silent server-side ceiling, not a countdown). **Voice-out** via `useSpeechOut.ts` → the
  server TTS endpoint (§9), with a mute toggle. tsc + eslint clean; `/tts` covered by
  `test_retrieval_api.py` (synthesizes · blank→400 · auth).

Related: [`retrieval-experience.md`](retrieval-experience.md) (the ambient-surface redesign this sits
inside), and the mode boundary in `backend/app/services/retrieval/modes.py`. Distinct from the
authored practice-test item (testbuilder) — don't merge.
