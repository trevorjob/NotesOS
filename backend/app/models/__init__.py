"""
NotesOS Models Package
"""

from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.models.course import Course, CourseEnrollment, Topic, CourseOutline
from app.models.resource import (
    Resource,
    ResourceFile,
    ResourceChunk,
    FactCheck,
    PreClassResearch,
    ResourceKind,
    SourceType,
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
from app.models.classmate import Class, Classmate


__all__ = [
    # User
    "User",
    "RefreshToken",
    # Course
    "Course",
    "CourseEnrollment",
    "Topic",
    "CourseOutline",
    # Resource
    "Resource",
    "ResourceFile",
    "ResourceChunk",
    "FactCheck",
    "PreClassResearch",
    "ResourceKind",
    "SourceType",
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
    # Classmates (Global Invites)
    "Class",
    "Classmate",
]
