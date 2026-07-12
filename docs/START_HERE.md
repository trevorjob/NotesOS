# NotesOS — Start Here (machine handoff)

> **Read this first on the new machine.** It's the single entry point: what won't
> transfer automatically, where the project stands, how to get it running on macOS
> from a fresh clone, and where to pick up. Everything else is linked from here.
>
> Last updated: 2026-07-11. Branch: `v2`.

---

## 0. What does NOT transfer automatically (do these by hand)

Git carries the code and these docs. It does **not** carry:

| Thing | Why | What to do on the Mac |
|---|---|---|
| **Uncommitted work** | Not in git until pushed | Commit + push `v2` on the old machine first (you're handling this). |
| **`.env` secrets** | Gitignored (API keys) | Copy `backend/.env` across securely (AirDrop/password manager). Template: `.env.example`. Keys listed in §3. **Fix `DATABASE_URL` to match the *new* machine's Docker Postgres** (`notesos:notesos_dev_password@localhost:5432/notesos`) — a copied `.env` carries the old box's DB name/password and fails auth on migrate. |
| **Local Postgres data** | Lives in a Docker volume | Nothing — v2 starts from a fresh DB (migrations are aggressive, no data to preserve). |
| **Claude Code memory** | Machine-local (`~/.claude/…`), not in the repo | Nothing to move — the durable decisions are captured in the repo docs (§1) and `CLAUDE.md`. A fresh Claude session rebuilds context by reading them. |
| **Git credentials** | The current remote URL has a PAT embedded in it | Re-auth on the Mac with `gh auth login` or SSH. Don't copy the token-in-URL; rotate that PAT. |

---

## 1. The docs, in reading order

| Doc | What it is |
|---|---|
| [`NotesOS—Product_Brief.md`](../NotesOS—Product_Brief.md) | What NotesOS is and why (product). |
| [`NotesOS_Architecture_NextPhase.md`](../NotesOS_Architecture_NextPhase.md) | **Canonical architecture** — the emergent-set model. Wins on any conflict. |
| [`Learning_Science—NotesOS_Design_Constraints.md`](../Learning_Science—NotesOS_Design_Constraints.md) | Learning-science principles as design constraints (retrieval, spacing, calibration). |
| [`docs/product-map.md`](./product-map.md) | Target feature surface + build status. The retrieval-engine bet lives here. |
| [`docs/v2-redesign-plan.md`](./v2-redesign-plan.md) | Execution plan + the **Launch build queue** ("all green ⇒ ship"), phase status, infra runbook. |
| [`docs/system-spec.md`](./system-spec.md) | **System-behaviour spec for the native-client designer** — how the systems work, states, timing, live vs. cached. |
| [`docs/build-guide.md`](./build-guide.md) | **Architect's guide for implementing agents** — invariants, codebase map, per-item traps, escalation triggers. Read before building a queue item. |
| [`CLAUDE.md`](../CLAUDE.md) | Project structure + working conventions (auto-loaded by Claude Code). |
| **This file** | Machine handoff + Mac setup. |

---

## 2. Where we are (state snapshot)

**Branch `v2`** is the rebuild. `main` / the live web app (**v1**) is a separate branch/env — leave it alone; changes here don't affect live users.

**Backend architecture — done (Phases 0–4, all tested):**
- **Phase 0** — test harness, enrollment-uniqueness integrity, hardened worker queue (retry/backoff/dead-letter).
- **Phase 1** — School entity + canonicalisation, user signals (program/entry_year/phone), user-created structured Terms; removed Semester/Class containers and public/private courses.
- **Phase 2** — proximity check on course creation (offer-or-fork).
- **Phase 3** — emergent-graph discovery (classmates + activity-gated feed, notify-don't-enroll); removed public course browse.
- **Phase 4** — Merge Agent quarantine gate (off-topic uploads held out of the shared note, uploader-only, auto-released on corroboration).

**Retrieval engine — pass 1 done (tested):** the substrate (`Concept` / `ConceptState` / `RetrievalAttempt`), FSRS scheduler, the mode-plugin abstraction + engine core, concept extraction wired into synthesis, and the existing **quiz migrated onto it as the first mode**. See §4.

**Retrieval engine — pass 2 done (tested):** ramble / teach / pretest as single-shot mode plugins, the HTTP session surface (`POST /api/retrieval/next` → `/attempt`, `GET /modes`), per-attempt calibration (predicted-vs-actual delta in the response), and a **dormant recognition seam** (`services/retrieval/recognition.py`, topic-level attribution, gated behind `ENABLE_RECOGNITION` — resolves beneficiaries but delivers nothing until §11 attribution + §9 digest land). No migration (the substrate already carried every field). 114 tests green.

**Migrations present** (`backend/alembic/versions/`): `…v2_baseline`, `…retrieval_substrate`, `…resource_quarantine_merge_gate`. Apply with `alembic upgrade head`.

**Test suites** (all green): `test_auth`, `test_courses`, `test_enrollment`, `test_schools`, `test_user_signals`, `test_terms`, `test_proximity`, `test_discovery`, `test_retrieval_scheduler`, `test_retrieval_concepts`, `test_retrieval_engine`, `test_quiz_mode`, `test_merge_gate`.

**Pending (next up):** multi-turn Socratic ramble/teach (the engine currently models one attempt per generate/evaluate — a dialogue needs session/turns state), subject-aware mode mixing off `subject_weight`, and wiring recognition **live** once the §11 attribution layer + §9 notification digest exist. After that, the launch bar is mostly product/design/ops/legal (see product-map §"Core vs. later").

---

## 3. Mac dev setup from scratch

### Prerequisites (Homebrew)
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install git python@3.12 node
brew install --cask docker    # Docker Desktop — launch it once so the daemon runs
```

### Clone + secrets
```bash
git clone https://github.com/trevorjob/NotesOS.git
cd NotesOS
git checkout v2
cp .env.example backend/.env   # then paste real values (see keys below)
```
Required `.env` keys (see `.env.example` for the full list):
`DATABASE_URL` (`postgresql+asyncpg://notesos:notesos_dev_password@localhost:5432/notesos`),
`REDIS_URL`, `JWT_SECRET`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `VOYAGE_AI_API_KEY`,
`CLOUDINARY_*`. Optional flags: `ENABLE_FACT_CHECK`, `ENABLE_PRE_CLASS_RESEARCH`, `ENABLE_VOICE_GRADING`.

### Start dependencies (Postgres + Redis)
`docker-compose.yml` provides Postgres (pgvector/pg16, user `notesos` / pw `notesos_dev_password` / db `notesos`) and Redis 7 — **no WSL, no native installs** (this is the big win vs. the Windows setup).
```bash
docker-compose up -d
```

### Backend
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # includes fsrs (spaced-repetition scheduler)

# extensions must exist before migrating (Vector + trigram columns)
psql "postgresql://notesos:notesos_dev_password@localhost:5432/notesos" \
  -c "CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pg_trgm;"

alembic upgrade head                      # applies the 3 migrations
python -m scripts.seed_schools            # seed the curated school catalogue

uvicorn app.main:app --reload             # API at http://localhost:8000/docs
python run_workers.py                     # (separate terminal) all 6 background workers
```

### Frontend
```bash
cd frontend
npm install
npm run dev                               # Next.js dev server
```
> Note: the frontend is **not** part of the current work (v2's client will be a native app). It stays as-is; don't build against it now.

### Tests
The suite runs against a **real Postgres** (schema built from the models, truncated between tests). Create the test DB and point `TEST_DATABASE_URL` at it:
```bash
psql "postgresql://notesos:notesos_dev_password@localhost:5432/postgres" \
  -c "CREATE DATABASE notesos_test;"
export TEST_DATABASE_URL="postgresql+asyncpg://notesos:notesos_dev_password@localhost:5432/notesos_test"
cd backend && pytest -q
```
The harness creates the `vector` + `pg_trgm` extensions in the test DB itself, so you only need the empty database. (The conftest default URL uses a different password — always set `TEST_DATABASE_URL` to match your local Postgres.)

---

## 4. The retrieval engine (newest subsystem) — orientation

The core product bet: **the retrieval engine is a set of pluggable *modes* over one
per-concept substrate**, not "quizzes." Full rationale in [`product-map.md`](./product-map.md).

```
backend/app/models/retrieval.py            Concept · ConceptState · RetrievalAttempt (the substrate)
backend/app/services/retrieval/
  scheduler.py     the ONLY file touching fsrs — grade → new FSRS schedule
  modes.py         the RetrievalMode Protocol (generate / evaluate / subject_weight)
  engine.py        mode-agnostic core: scope selection, attempt recording, scheduling
  concepts.py      elevate TopicKnowledge.concepts → first-class Concept rows (at synthesis)
  quiz_mode.py     the first mode plugin (wraps existing call_llm + grader)
  registry.py      key → mode lookup (register ramble/teach/pretest here later)
```
Mental model: **topic = what the user consumes; concept = what the app measures.** A
mode poses a challenge for a concept and judges the response into a grade; the engine
records the append-only attempt and advances the FSRS schedule. Adding a mode is a new
file implementing the Protocol + one `register()` line — nothing else changes.

---

## 5. Working conventions (how this rebuild is run)

These were the standing rules for the whole v2 effort. Keep them:

- **Backend-only.** Don't touch the Next.js frontend — the v2 client is a native app (designs pending).
- **v1 is separate.** The live web app lives on its own branch/env. Hard deletes here are safe.
- **No hand-written migrations.** Models are the source of truth; run `alembic revision --autogenerate` after model changes. Extensions go in `init_db()`; seed data in `scripts/`.
- **Infra is the owner's job.** Claude writes code + tests and documents infra steps; you run docker/DB/migrations/installs.
- **Tests guard the surgery.** New logic ships with tests against real Postgres.

---

## 6. Pick up here

**The product design phase is complete (2026-07-11).** The whole surface was walked and every
decision is captured as a `LOCKED` note in [`product-map.md`](./product-map.md) — the
notification/habit model, access & payment, the Consolidated Note, retrieval session feel,
daily entry point, progress-without-streaks, Listen + tutor, onboarding, capture
(dump-then-auto-organize + outline scaffold + audio), STEM parity / subject families,
offline/sync, and synchronous-communal. **We are done planning; now we build.**

Two docs carry it forward:
- **What to build, in order:** the **Launch build queue** in
  [`v2-redesign-plan.md`](./v2-redesign-plan.md) — a checkable "all green ⇒ ship" list.
  **Start at Phase A** (backend, no native dependency):
  1. **A1 · Streaming + model tiering** (`call_llm_stream`; fast/heavy routing) — the cheap
     warm-up; speed *and* cost.
  2. **A2 · Capture overhaul** (audio ingestion; dump→auto-organize; outline scaffold) — the
     highest-felt build; the front door.
  3. **A3 · Session + Recap** (session from the attempt log; recap mode) — keystone.
  4. **A4 · Incremental synthesis** (append-merge, not rebuild) — kills the cost bomb.
- **How the systems behave** (for the native-client designer, and as the build contract):
  [`system-spec.md`](./system-spec.md).

**Recommended first move:** A1, then A2. Each item's acceptance bar ("Green when…") is in the
build queue; behaviour details are in the system spec.
