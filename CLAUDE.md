# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NotesOS is a collaborative AI-powered study platform. Students upload course resources (PDFs, notes, DOCX), and the system auto-generates quizzes, fact-checks content, provides AI tutoring, and tracks mastery — with real-time collaboration via WebSockets.

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
| Workers | 6 async Redis-queue workers |
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

**Stores (`stores/`):** `auth`, `courses`, `tests`, `resources`, `knowledge`, `notifications`, `aiChat`, `progress`

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

**Services (`services/`):** Each service is a focused module — `rag.py`, `grader.py`, `question_generator.py`, `knowledge_synthesizer.py`, `vector_store.py`, `file_processor.py`, `hybrid_ocr.py`, `study_agent.py`, `cache.py`, `websocket.py`, `storage.py`, etc.

**Background workers (`workers/`):** Started via `run_workers.py` with `asyncio.gather()`. Workers read from Redis queues and do heavy async work outside the request path:
- `chunking_worker` — Split resources into chunks + generate embeddings
- `knowledge_worker` — Synthesize knowledge summaries via LangChain + Claude
- `fact_check_worker` — Verify claims in notes
- `grading_worker` — AI-grade voice/text quiz answers (LangGraph)
- `transcription_worker` — Whisper audio-to-text
- `audio_worker` — TTS audio generation

**Database (`database.py`):** Async SQLAlchemy engine with `pool_size=2, max_overflow=3` (each process manages its own pool). `init_db()` creates tables on startup. Use `get_db()` as a FastAPI dependency; use `worker_session()` context manager in workers.

**Models (`models/`):** `user`, `course`, `resource`, `test`, `progress`, `knowledge`, `semester`, `notification`, `classmate`.

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
