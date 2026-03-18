"""
NotesOS Models Package
"""

from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.models.course import Course, CourseEnrollment, Topic, CourseOutline
from app.models.semester import Semester, SemesterMember, SemesterRole
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
    AnswerStatus,
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
from app.models.notification import Notification, NotificationType
from app.models.knowledge import TopicKnowledge, AudioLesson, KnowledgeStatus


__all__ = [
    # User
    "User",
    "RefreshToken",
    # Course
    "Course",
    "CourseEnrollment",
    "Topic",
    "CourseOutline",
    # Semester
    "Semester",
    "SemesterMember",
    "SemesterRole",
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
    "AnswerStatus",
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
    # Notifications
    "Notification",
    "NotificationType",
    # Knowledge
    "TopicKnowledge",
    "AudioLesson",
    "KnowledgeStatus",
]
