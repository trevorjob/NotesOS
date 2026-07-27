# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NotesOS is a collaborative AI-powered study platform. Students upload course resources (PDFs, notes, DOCX), and the system auto-generates quizzes, fact-checks content, provides AI tutoring, and tracks mastery — with real-time collaboration via WebSockets.

> **On branch `v2`? Read [`docs/START_HERE.md`](docs/START_HERE.md) first.** It's the
> entry point for the ongoing rebuild: current state, the doc map, Mac setup, and where
> to pick up. Canonical architecture is [`NotesOS_Architecture_NextPhase.md`](NotesOS_Architecture_NextPhase.md)
> (wins on conflict); the feature target is [`docs/product-map.md`](docs/product-map.md);
> execution status is [`docs/v2-redesign-plan.md`](docs/v2-redesign-plan.md).
>
> **Building a queue item? Read [`docs/build-guide.md`](docs/build-guide.md) first** — the
> architect's guide: the non-negotiable invariants, how the codebase actually behaves, per-item
> traps, and when to escalate an architecture decision instead of deciding solo. The
> designer-facing behaviour contract is [`docs/system-spec.md`](docs/system-spec.md).
>
> **v2 working conventions (keep these):** backend-only (don't touch the Next.js
> frontend — v2's client is a native app); v1 is a separate branch/env; **never
> hand-write Alembic migrations** (keep models correct, run `alembic revision
> --autogenerate`); extensions go in `init_db()`, seed data in `scripts/`; new logic
> ships with tests against a real Postgres.

## Development Commands

### Setup

```bash
# Start local dependencies (PostgreSQL + Redis)
docker-compose up -d
```

### Backend

```bash
wsl
cd backend
source .venv/bin/activate
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start API server (dev, with auto-reload)
uvicorn app.main:app --reload

# Start all background workers
python run_workers.py
```

### Frontend

```bash
cd frontend
npm install

# Dev server (uses webpack, not Turbopack)
npm run dev

# Production build
npm run build

# Lint
npm run lint
```

### API Docs

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Architecture

### Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js (App Router), React 19, TypeScript |
| State | Zustand with localStorage persistence |
| Backend | FastAPI (Python), async SQLAlchemy 2.0 |
| Database | PostgreSQL 16 + pgvector (1536-dim embeddings) |
| Cache / Real-time | Redis 7 (pub/sub for WebSocket broadcast) |
| Workers | 7 async Redis-queue workers + a periodic digest scheduler |
| AI | Deepseek, rrAnthropic Claude, OpenAI GPT-4o/Whisper, Voyage AI |
| File Storage | Cloudinary (S3-compatible R2) |
| Auth | JWT (15 min access / 7 day refresh) + Google OAuth |

---

### Frontend (`frontend/src/`)

**Route groups:**
- `app/(auth)/` — Login, register (public)
- `app/(app)/` — All protected routes; layout enforces auth

**Key protected routes:**
- `home` — Dashboard
- `courses/[courseId]/topics/[topicId]` — Topic learning view
- `courses/[courseId]/topics/[topicId]/quiz` — Quiz interface
- `progress` — Study stats & streaks
- `settings` — User personality preferences
- `generate-test` — AI quiz generation

**Stores (`stores/`):** `auth`, `courses`, `tests`, `resources`, `knowledge`, `notifications`, `aiChat`, `progress`, `semesters`

**API layer (`lib/api.ts`):** Axios instance with JWT interceptor. On 401, queues in-flight requests, refreshes the token, then retries. Base URL from `NEXT_PUBLIC_API_URL`.

**WebSocket (`lib/websocket.ts`):** Connects to `WS /ws/{course_id}?token={jwt}`. Handles `active_users`, `user_joined`, `user_left`, `course_updated` events.

---

### Backend (`backend/app/`)

**Entry point:** `main.py` — Registers all routers, CORS, Gzip middleware, lifespan (init_db + Redis listener startup).

**API routes:**
- `/api/auth` — Login, register, refresh, Google OAuth, personality
- `/api/courses` — CRUD, invite/join
- `/api/{course_id}/topics` — Topic management
- `/api/{course_id}/topics/{topic_id}/resources` — File upload & retrieval
- `/api/ai/*` — Grading, fact-check, pre-class research, AI chat
- `/api/progress` — Mastery tracking
- `/api/knowledge` — RAG knowledge base
- `/api/notifications` — Alert management
- `/api/semesters` — Course grouping

**Services (`services/`):** Each service is a focused module — `rag.py`, `grader.py`, `knowledge_synthesizer.py`, `vector_store.py`, `file_processor.py`, `hybrid_ocr.py`, `study_agent.py`, `cache.py`, `websocket.py`, `storage.py`, `retrieval/` (the engine + modes), etc.

**Background workers (`workers/`):** Started via `run_workers.py` with `asyncio.gather()`. Workers drain Redis queues via the shared `run_worker_loop` (retry/backoff/dead-letter) and do heavy async work outside the request path:
- `chunking_worker` — Split resources into chunks + generate embeddings
- `knowledge_worker` — Merge-gate + synthesize the consolidated note (incremental)
- `fact_check_worker` — Verify claims in notes (flag-gated)
- `transcription_worker` — Whisper audio-to-text (ingestion front door)
- `audio_worker` — TTS audio generation
- `capture_worker` — Dump → auto-organize a bulk upload into topics
- `practice_test_worker` — Generate an authored practice-test question set (B14)
- `notification_scheduler` — Periodic (APScheduler) habit digest, not queue-driven

> Retired with the v1 test system (2026-07-26): `grading_worker` (v2 grades
> synchronously in `POST /retrieval/attempt`) and `test_generation_worker` (v2
> generates on demand; B14's `practice_test_worker` is the bounded, atom-feeding
> replacement, not a resurrection).

**Database (`database.py`):** Async SQLAlchemy engine with `pool_size=2, max_overflow=3` (each process manages its own pool). `init_db()` creates tables on startup. Use `get_db()` as a FastAPI dependency; use `worker_session()` context manager in workers.

**Models (`models/`):** `user`, `course` (+ `Topic`, `CourseEnrollment`, `CourseOutline`), `resource`, `subject`, `retrieval` (`Concept`/`ConceptState`/`RetrievalAttempt`), `consume`, `practice_test` (B14), `progress`, `knowledge`, `term`, `school`, `notification`, `report`. (The v1 `test`/`semester`/`classmate` container models were removed in the v2 rebuild.)

---

### Real-time Flow

1. Resource uploaded → chunking task pushed to Redis queue
2. `chunking_worker` processes chunks, generates embeddings, pushes knowledge synthesis task
3. `knowledge_worker` runs LangChain synthesis, stores result, broadcasts WebSocket event to course room
4. Frontend receives WebSocket event, updates Zustand store

---

### Environment Variables

Copy `.env.example`. Required keys:
- `DATABASE_URL` — `postgresql+asyncpg://...`
- `REDIS_URL`
- `JWT_SECRET`
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `VOYAGE_AI_API_KEY`
- `CLOUDINARY_*`

Optional feature flags: `ENABLE_FACT_CHECK`, `ENABLE_PRE_CLASS_RESEARCH`, `ENABLE_VOICE_GRADING`

---

### Database Migrations

```bash
# Generate a new migration after model changes
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

---

## Key Conventions

### Backend Conventions

- **Sessions:** Use `get_db()` (FastAPI dep) in routes, `worker_session()` (context manager) in workers — never mix them.
- **Cache invalidation:** Redis cache keys follow `{resource}:{id}` pattern. Invalidate on any write by calling `cache.delete(key)` in the route handler after DB commit.
- **New API route:** Create file in `api/`, define router, register in `main.py` under the correct prefix.
- **New worker:** Add to `workers/`, import and add coroutine to `asyncio.gather()` in `run_workers.py`.
- **Async everywhere:** All DB calls must be `await`ed. Never use sync SQLAlchemy calls.
- **Migrations:** Always run `alembic revision --autogenerate` after model changes — never edit tables manually.

### Frontend Conventions

- **API calls:** Always go through `lib/api.ts` — never use `fetch` or a bare axios instance.
- **State:** All server state lives in Zustand stores. Components read from stores, not local state where avoidable.
- **WebSocket events:** Handle in the store action that owns the related data, not in components.
- **New store:** Follow existing pattern — define state interface, actions, and `persist` middleware if needed.
- **Route protection:** Handled by `app/(app)/layout.tsx` — no per-page auth checks needed.

### Global Workflow (from `~/.claude/CLAUDE.md`)

The global config covers: TDD workflow, agent usage, git commit format (`feat/fix/refactor/...`), security checklist, and code quality standards. Refer to it for process — this file covers project-specific structure only.

---

## Design Context

> Full design system details live in `.impeccable.md`. This section is the always-loaded summary.

### Users
Students (undergrads, self-directed learners) during active study sessions. They want to understand material, not just collect it. The interface competes with distraction — it must feel satisfying and personal.

### Brand Personality
**Creative, playful, bright.** Encouraging without being patronising. Speaks like a brilliant, slightly irreverent study partner. Short sentences. Light in tone. Active UI copy ("Let's see what you know" beats "Start quiz").

**NOT:** edtech corporate, children's app, productivity minimalism, grunge/distressed.

### Aesthetic Direction — Notebook
The app feels like a creative student's physical notebook come to life. Texture and humanity on every surface. Half notebook, half polished app — the craft is the supporting character, content leads.

**Key implementation details:**
- **Background:** `#F5F3EE` warm cream + SVG noise/grain at 4–6% opacity. Never flat.
- **Highlighter accent:** `rgba(217, 119, 6, 0.2)` semi-transparent amber — NOT flat amber. Used for active states, selected items, quiz correct answers.
- **Caveat font** (Google Fonts, handwriting): small labels, annotations, metadata, breadcrumbs only. Never body text or headings.
- **Notebook ruled lines:** 28px apart, 6% opacity, `#8B7355` — behind consolidated note sections only.
- **Rough card borders:** SVG filter on consolidated note card and key points card only. Other cards stay clean.
- **Hand-drawn SVG illustrations:** Empty states, section headers, loading states, focus mode margins. Ink-line / stipple style. Single colour (warm grey or amber).
- **Focus mode margin doodles:** Static SVG doodles in left/right margins at viewport > 1100px.
- **Dark mode — Night Journal:** Deep warm darks (`#1C1A17` base), same grain, amber accent glows slightly more vivid.

### Design Principles
1. **Texture before flatness** — every surface has weight and grain.
2. **Playful restraint** — hand-drawn accents amplify content, never compete.
3. **Study-forward** — delight is the retention mechanism, not decoration.
4. **Notebook logic** — if it would exist in a well-loved student's notebook, it belongs here.
5. **Both modes, same soul** — warm paper (light) and night journal (dark), same amber + grain constants.

### Accessibility
WCAG AA throughout. Grain never impedes text legibility. Illustrations are `aria-hidden`. Caveat font only for non-critical labels. Respect `prefers-reduced-motion`.
