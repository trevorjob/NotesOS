"""
NotesOS Backend - Main Application Entry Point
"""

from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from jose import jwt, JWTError

from app.config import settings
from app.database import init_db
from app.core.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    # Startup
    await init_db()
    logger.info("Database initialised")
    # Start Redis listeners for course updates and user notifications
    from app.services.websocket import connection_manager

    await connection_manager.start_redis_listener()

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
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Compress JSON / text responses ≥ 1 KB
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Request/response logging + X-Request-ID header
from app.middleware.logging import RequestLoggingMiddleware
app.add_middleware(RequestLoggingMiddleware)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"message": "NotesOS API is running", "version": "0.1.0"}


@app.get("/health")
async def health_check():
    """Detailed health check — actually verifies DB and Redis connectivity."""
    import time
    from sqlalchemy import text
    from app.database import async_session_maker
    from app.services.redis_client import redis_client

    checks: dict = {}
    overall = "healthy"

    # Database
    t0 = time.monotonic()
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = {"status": "ok", "latency_ms": round((time.monotonic() - t0) * 1000, 1)}
    except Exception as e:
        checks["database"] = {"status": "error", "error": str(e)}
        overall = "degraded"

    # Redis
    t0 = time.monotonic()
    try:
        r = await redis_client.get_client()
        await r.ping()
        checks["redis"] = {"status": "ok", "latency_ms": round((time.monotonic() - t0) * 1000, 1)}
    except Exception as e:
        checks["redis"] = {"status": "error", "error": str(e)}
        overall = "degraded"

    status_code = 200 if overall == "healthy" else 503
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=status_code,
        content={"status": overall, "checks": checks},
    )


# Import and include routers
from app.api import auth_router, courses_router
from app.api.topics import router as topics_router
from app.api.resources import router as resources_router
from app.api.invites import router as invites_router
from app.api.ai_features import router as ai_features_router
from app.api.progress import router as progress_router
from app.api.semesters import router as semesters_router
from app.api.notifications import router as notifications_router
from app.api.knowledge import router as knowledge_router
from app.services.websocket import connection_manager

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(courses_router, prefix="/api/courses", tags=["courses"])
app.include_router(topics_router, prefix="/api", tags=["topics"])
app.include_router(resources_router, prefix="/api", tags=["resources"])
app.include_router(invites_router, prefix="/api/invites", tags=["invites"])
app.include_router(ai_features_router, prefix="", tags=["AI Features"])
app.include_router(progress_router, prefix="", tags=["Progress"])
app.include_router(semesters_router, prefix="/api/semesters", tags=["semesters"])
app.include_router(
    notifications_router, prefix="/api/notifications", tags=["notifications"]
)
app.include_router(knowledge_router, prefix="/api", tags=["knowledge"])


# WebSocket endpoint for real-time updates

@app.websocket("/ws/{course_id}")
async def websocket_endpoint(
    websocket: WebSocket, course_id: str, token: str = Query(...)
):
    """
    WebSocket connection for real-time course updates.

    Query params:
        token: JWT authentication token
    """
    # Authenticate via token.
    # Must accept() before close() — otherwise Starlette responds with HTTP 403
    # instead of a proper WebSocket close code, causing the client to loop forever.
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            await websocket.accept()
            await websocket.close(code=1008)
            return
    except JWTError:
        await websocket.accept()
        await websocket.close(code=1008)
        return

    # Connect (connection_manager.connect calls websocket.accept() internally)
    await connection_manager.connect(websocket, course_id, user_id)

    try:
        # Send active users list
        active_users = connection_manager.get_active_users(course_id)
        await connection_manager.send_personal_message(
            websocket, {"type": "active_users", "users": list(active_users)}
        )

        # Keep connection alive and listen for messages
        while True:
            data = await websocket.receive_text()
            try:
                import json as _json
                msg = _json.loads(data)
                if msg.get("type") == "ping":
                    await connection_manager.send_personal_message(websocket, {"type": "pong"})
                else:
                    await connection_manager.send_personal_message(websocket, {"type": "echo", "data": data})
            except Exception:
                pass

    except WebSocketDisconnect:
        user_id = connection_manager.disconnect(websocket, course_id)

        # Notify others
        if user_id:
            await connection_manager.broadcast_to_course(
                course_id, {"type": "user_left", "user_id": user_id}
            )


# Future routers (Phase 3):
# from app.api import study, tests, ai, progress
# app.include_router(study.router, prefix="/api/study", tags=["study"])
# app.include_router(tests.router, prefix="/api/tests", tags=["tests"])
# app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
# app.include_router(progress.router, prefix="/api/progress", tags=["progress"])
