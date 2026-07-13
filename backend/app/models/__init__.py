"""
NotesOS Models Package
"""

from app.models.user import User
from app.models.refresh_token import RefreshToken
from app.models.school import School
from app.models.term import Term, DivisionType
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
from app.models.notification import Notification, NotificationType
from app.models.knowledge import TopicKnowledge, AudioLesson, KnowledgeStatus
from app.models.retrieval import Concept, ConceptState, RetrievalAttempt
from app.models.consume import ConsumeEvent, ConsumeKind


__all__ = [
    # User
    "User",
    "RefreshToken",
    # School
    "School",
    # Term
    "Term",
    "DivisionType",
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
    "AnswerStatus",
    # Progress
    "StudySession",
    "UserProgress",
    "AIConversation",
    "AIMessage",
    "SessionType",
    "MessageRole",
    # Notifications
    "Notification",
    "NotificationType",
    # Knowledge
    "TopicKnowledge",
    "AudioLesson",
    "KnowledgeStatus",
    # Retrieval substrate
    "Concept",
    "ConceptState",
    "RetrievalAttempt",
    # Consume-event substrate (§11 attribution / recognition)
    "ConsumeEvent",
    "ConsumeKind",
]
