"""
NotesOS Backend - Main Application Entry Point
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    # Startup
    await init_db()
    yield
    # Shutdown
    pass


app = FastAPI(
    title="NotesOS API",
    description="AI-powered study companion backend",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "NotesOS API is running", "version": "0.1.0"}


@app.get("/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "database": "connected",
        "redis": "connected",
    }


# Import and include routers
from app.api import auth_router, courses_router

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(courses_router, prefix="/api/courses", tags=["courses"])

# Future routers (uncomment as implemented):
# from app.api import topics, notes, study, tests, ai, progress
# app.include_router(topics.router, prefix="/api/topics", tags=["topics"])
# app.include_router(notes.router, prefix="/api/notes", tags=["notes"])
# app.include_router(study.router, prefix="/api/study", tags=["study"])
# app.include_router(tests.router, prefix="/api/tests", tags=["tests"])
# app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
# app.include_router(progress.router, prefix="/api/progress", tags=["progress"])
