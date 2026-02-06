"""
NotesOS Models Package
"""

from app.models.user import User
from app.models.course import Course, CourseEnrollment, Topic, CourseOutline
from app.models.note import (
    Note,
    NoteChunk,
    NoteVersion,
    FactCheck,
    PreClassResearch,
    ContentType,
    VerificationStatus,
)
from app.models.test import (
    Test,
    TestQuestion,
    TestAttempt,
    TestAnswer,
    TestType,
    QuestionType,
)
from app.models.progress import (
    StudySession,
    UserProgress,
    AIConversation,
    AIMessage,
    SessionType,
    MessageRole,
)

__all__ = [
    # User
    "User",
    # Course
    "Course",
    "CourseEnrollment",
    "Topic",
    "CourseOutline",
    # Note
    "Note",
    "NoteChunk",
    "NoteVersion",
    "FactCheck",
    "PreClassResearch",
    "ContentType",
    "VerificationStatus",
    # Test
    "Test",
    "TestQuestion",
    "TestAttempt",
    "TestAnswer",
    "TestType",
    "QuestionType",
    # Progress
    "StudySession",
    "UserProgress",
    "AIConversation",
    "AIMessage",
    "SessionType",
    "MessageRole",
]
