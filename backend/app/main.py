"""
NotesOS Backend - Main Application Entry Point
"""

from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt, JWTError

from app.config import settings
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    # Startup
    await init_db()

    # Start Redis listener for worker updates
    # Import here to ensure connection_manager is initialized
    from app.services.websocket import connection_manager

    asyncio.create_task(connection_manager.start_redis_listener())

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
from app.api.topics import router as topics_router
from app.api.resources import router as resources_router
from app.api.invites import router as invites_router
from app.api.ai_features import router as ai_features_router
from app.api.progress import router as progress_router
from app.services.websocket import connection_manager

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(courses_router, prefix="/api/courses", tags=["courses"])
app.include_router(topics_router, prefix="/api", tags=["topics"])
app.include_router(resources_router, prefix="/api", tags=["resources"])
app.include_router(invites_router, prefix="/api/invites", tags=["invites"])
app.include_router(ai_features_router, prefix="", tags=["AI Features"])
app.include_router(progress_router, prefix="", tags=["Progress"])


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
    # Authenticate via token
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            await websocket.close(code=1008)  # Policy violation
            return
    except JWTError:
        await websocket.close(code=1008)
        return

    # Connect
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
            # Echo back for now (can add more logic later)
            await connection_manager.send_personal_message(
                websocket, {"type": "echo", "data": data}
            )

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
