"""
NotesOS API Package
"""

from app.api.auth import router as auth_router
from app.api.courses import router as courses_router

__all__ = [
    "auth_router",
    "courses_router",
]
