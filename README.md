# NotesOS

**Your AI Study Companion** - Study smarter, together. Your notes, your AI, your success.

## Overview

NotesOS is an AI-powered collaborative study platform where students share notes, get AI-assisted study help, take voice-graded quizzes, and track their learning progress.

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14, React, Zustand, TailwindCSS, shadcn/ui |
| Backend | Python FastAPI, LangGraph, LangChain |
| AI | Claude Sonnet 4.5, OpenAI Whisper, Voyage AI |
| Database | PostgreSQL + pgvector, Redis |
| Storage | Cloudflare R2 (S3-compatible) |

## Project Structure

```
NotesOS/
├── frontend/          # Next.js 14 App
├── backend/           # FastAPI Backend
├── docker-compose.yml # Local dev (Postgres + Redis)
└── .env.example       # Environment template
```

## Quick Start

### Prerequisites

- Node.js 18+
- Python 3.11+
- Docker & Docker Compose

### 1. Start Database Services

```bash
docker-compose up -d
```

### 2. Backend Setup

```bash
cd backend
python -m venv venv
.\venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

pip install -r requirements.txt
cp ../.env.example .env
# Edit .env with your API keys

uvicorn app.main:app --reload
```

Backend runs at: http://localhost:8000

### 3. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at: http://localhost:3000

## API Documentation

When the backend is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Key Features

- **Shared Knowledge Pool** - Collaborative note sharing
- **AI Study Partner** - Personalized AI with adjustable personality
- **Voice-First Studying** - Record answers, get AI grading
- **Fact Checker** - Automatic verification of note claims
- **Pre-Class Research** - AI-generated topic primers
- **Progress Tracking** - Mastery levels and study streaks

## License

MIT
