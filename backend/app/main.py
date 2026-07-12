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
from app.api.ai_features import router as ai_features_router
from app.api.progress import router as progress_router
from app.api.notifications import router as notifications_router
from app.api.knowledge import router as knowledge_router
from app.api.schools import router as schools_router
from app.api.terms import router as terms_router
from app.api.discovery import router as discovery_router
from app.api.retrieval import router as retrieval_router
from app.api.capture import router as capture_router
from app.services.websocket import connection_manager

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(courses_router, prefix="/api/courses", tags=["courses"])
app.include_router(topics_router, prefix="/api", tags=["topics"])
app.include_router(resources_router, prefix="/api", tags=["resources"])
app.include_router(ai_features_router, prefix="", tags=["AI Features"])
app.include_router(progress_router, prefix="", tags=["Progress"])
app.include_router(
    notifications_router, prefix="/api/notifications", tags=["notifications"]
)
app.include_router(knowledge_router, prefix="/api", tags=["knowledge"])
app.include_router(schools_router, prefix="/api/schools", tags=["schools"])
app.include_router(terms_router, prefix="/api/terms", tags=["terms"])
app.include_router(discovery_router, prefix="/api/discovery", tags=["discovery"])
app.include_router(retrieval_router, tags=["retrieval"])  # self-prefixed /api/retrieval
app.include_router(capture_router, prefix="/api", tags=["capture"])


# WebSocket endpoint for user-scoped events (test generation, personal notifications)
# IMPORTANT: must be defined BEFORE /ws/{course_id} to avoid route shadowing.

@app.websocket("/ws/user/{user_id}")
async def websocket_user_endpoint(
    websocket: WebSocket, user_id: str, token: str = Query(...)
):
    """
    User-scoped WebSocket for personal events (test generation progress, etc.).
    Unlike /ws/{course_id}, this is not broadcast to a room — events are sent
    only to the authenticated user.
    """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        token_user_id: str = payload.get("sub")
        if token_user_id is None or token_user_id != user_id:
            await websocket.accept()
            await websocket.close(code=1008)
            return
    except JWTError:
        await websocket.accept()
        await websocket.close(code=1008)
        return

    # Reuse the same connection_manager — send_to_user already works per user_id.
    # We register this connection under a synthetic "course_id" of __user__{user_id}
    # so the manager's room bookkeeping doesn't clash with real course rooms.
    virtual_room = f"__user__{user_id}"
    await connection_manager.connect(websocket, virtual_room, user_id)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                import json as _json
                msg = _json.loads(data)
                if msg.get("type") == "ping":
                    await connection_manager.send_personal_message(websocket, {"type": "pong"})
            except Exception:
                pass
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket, virtual_room)


# WebSocket endpoint for real-time course updates

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
