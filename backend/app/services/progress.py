"""
NotesOS - Progress Service
Track study sessions, calculate mastery, maintain streaks, generate recommendations.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import uuid

from app.models.progress import StudySession, UserProgress, SessionType
from app.models.test import TestAttempt, Test


class ProgressService:
    """Service for tracking and calculating student progress."""

    async def start_session(
        self,
        db: AsyncSession,
        user_id: str,
        topic_id: str,
        session_type: str = "reading",
    ) -> StudySession:
        """
        Start a study session.

        Args:
            db: Database session
            user_id: User ID
            topic_id: Topic ID
            session_type: reading, quiz, or practice

        Returns:
            Created StudySession
        """
        session = StudySession(
            user_id=uuid.UUID(user_id),
            topic_id=uuid.UUID(topic_id),
            session_type=SessionType[session_type.upper()],
            started_at=datetime.utcnow(),
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    async def end_session(self, db: AsyncSession, session_id: str) -> StudySession:
        """
        End a study session and update progress.

        Args:
            db: Database session
            session_id: Session ID

        Returns:
            Updated StudySession
        """
        # Get session
        query = select(StudySession).where(StudySession.id == uuid.UUID(session_id))
        result = await db.execute(query)
        session = result.scalar_one_or_none()

        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Calculate duration
        session.ended_at = datetime.utcnow()
        session.duration_seconds = int(
            (session.ended_at - session.started_at).total_seconds()
        )

        # Update user progress
        await self._update_user_progress(
            db, str(session.user_id), str(session.topic_id), session.duration_seconds
        )

        await db.commit()
        await db.refresh(session)
        return session

    async def calculate_mastery(
        self, db: AsyncSession, user_id: str, topic_id: str
    ) -> float:
        """
        Calculate mastery level for a topic.

        Formula: (quiz_score × 0.4) + (study_time × 0.3) + (consistency × 0.3)
        - quiz_score: avg test score for topic (0-1)
        - study_time: normalized hours (0-1, capped at 10 hours)
        - consistency: sessions in last 7 days / 7 (0-1)

        Returns:
            Mastery level (0.00 - 1.00)
        """
        user_uuid = uuid.UUID(user_id)
        topic_uuid = uuid.UUID(topic_id)

        # 1. Quiz score (40%)
        quiz_score = await self._get_avg_quiz_score(db, user_uuid, topic_uuid)

        # 2. Study time (30%)
        study_time_score = await self._get_study_time_score(db, user_uuid, topic_uuid)

        # 3. Consistency (30%)
        consistency_score = await self._get_consistency_score(db, user_uuid, topic_uuid)

        # Weighted formula
        mastery = (
            (float(quiz_score) * 0.4)
            + (float(study_time_score) * 0.3)
            + (float(consistency_score) * 0.3)
        )
        return round(mastery, 2)

    async def update_streak(
        self, db: AsyncSession, user_id: str, course_id: str
    ) -> int:
        """
        Update study streak for a course.
        Streak resets if no activity for >24 hours.

        Args:
            db: Database session
            user_id: User ID
            course_id: Course ID

        Returns:
            Current streak days
        """
        user_uuid = uuid.UUID(user_id)
        course_uuid = uuid.UUID(course_id)

        # Get all progress records for course
        query = select(UserProgress).where(
            UserProgress.user_id == user_uuid,
            UserProgress.course_id == course_uuid,
        )
        result = await db.execute(query)
        progress_records = result.scalars().all()

        if not progress_records:
            return 0

        # Check most recent activity across all topics
        latest_activity = max(rec.last_activity for rec in progress_records)
        hours_since_activity = (
            datetime.utcnow() - latest_activity
        ).total_seconds() / 3600

        # Update streak for all records
        for record in progress_records:
            if hours_since_activity > 24:
                # Reset streak
                record.streak_days = 1
            else:
                # Check if already counted today
                last_streak_date = record.last_activity.date()
                today = datetime.utcnow().date()

                if last_streak_date < today:
                    record.streak_days += 1

            record.last_activity = datetime.utcnow()

        await db.commit()

        # Return max streak across all topics
        return max(rec.streak_days for rec in progress_records)

    async def get_recommendations(
        self, db: AsyncSession, user_id: str, course_id: str
    ) -> List[Dict[str, Any]]:
        """
        Generate study recommendations.

        Recommends:
        1. Weakest topics (mastery < 0.5)
        2. Topics not studied recently (>3 days)
        3. Next logical topic (sequential order)

        Returns:
            List of recommendations with topic_id, reason, priority
        """
        user_uuid = uuid.UUID(user_id)
        course_uuid = uuid.UUID(course_id)

        recommendations = []

        # Get all progress for course
        query = select(UserProgress).where(
            UserProgress.user_id == user_uuid,
            UserProgress.course_id == course_uuid,
        )
        result = await db.execute(query)
        progress_records = result.scalars().all()

        # 1. Weak topics
        for record in progress_records:
            if record.mastery_level < 0.5:
                recommendations.append(
                    {
                        "topic_id": str(record.topic_id),
                        "reason": f"Low mastery ({record.mastery_level:.0%})",
                        "priority": "high",
                        "type": "weak_topic",
                    }
                )

        # 2. Topics not studied recently
        three_days_ago = datetime.utcnow() - timedelta(days=3)
        for record in progress_records:
            if record.last_activity < three_days_ago:
                days_ago = (datetime.utcnow() - record.last_activity).days
                recommendations.append(
                    {
                        "topic_id": str(record.topic_id),
                        "reason": f"Not studied in {days_ago} days",
                        "priority": "medium",
                        "type": "inactive_topic",
                    }
                )

        return recommendations[:5]  # Top 5 recommendations

    # ── Private Helper Methods ──────────────────────────────────────────────

    async def _update_user_progress(
        self, db: AsyncSession, user_id: str, topic_id: str, duration_seconds: int
    ):
        """Update UserProgress record after a session."""
        user_uuid = uuid.UUID(user_id)
        topic_uuid = uuid.UUID(topic_id)

        # Get or create progress record
        query = select(UserProgress).where(
            UserProgress.user_id == user_uuid,
            UserProgress.topic_id == topic_uuid,
        )
        result = await db.execute(query)
        progress = result.scalar_one_or_none()

        if not progress:
            # Get course_id from topic (simplified - should join)
            from app.models.course import Topic

            topic_query = select(Topic).where(Topic.id == topic_uuid)
            topic_result = await db.execute(topic_query)
            topic = topic_result.scalar_one()

            progress = UserProgress(
                user_id=user_uuid,
                course_id=topic.course_id,
                topic_id=topic_uuid,
            )
            db.add(progress)

        # Update study time
        progress.total_study_time = (progress.total_study_time or 0) + duration_seconds
        progress.last_activity = datetime.utcnow()

        # Recalculate mastery
        progress.mastery_level = await self.calculate_mastery(db, user_id, topic_id)

        await db.commit()

    async def _get_avg_quiz_score(
        self, db: AsyncSession, user_id: uuid.UUID, topic_id: uuid.UUID
    ) -> float:
        """Get average quiz score for a topic (0-1 scale)."""
        # Get all test attempts for this topic
        query = (
            select(TestAttempt)
            .join(Test)
            .where(
                TestAttempt.user_id == user_id,
                Test.topics.contains([str(topic_id)]),  # Topic in topics array
                TestAttempt.completed_at.isnot(None),
            )
        )
        result = await db.execute(query)
        attempts = result.scalars().all()

        if not attempts:
            return 0.0

        # Calculate average score (normalize to 0-1)
        avg_score = sum(a.total_score / a.max_score for a in attempts) / len(attempts)
        return min(1.0, avg_score)

    async def _get_study_time_score(
        self, db: AsyncSession, user_id: uuid.UUID, topic_id: uuid.UUID
    ) -> float:
        """Get normalized study time score (0-1, capped at 10 hours)."""
        query = select(UserProgress).where(
            UserProgress.user_id == user_id,
            UserProgress.topic_id == topic_id,
        )
        result = await db.execute(query)
        progress = result.scalar_one_or_none()

        if not progress or not progress.total_study_time:
            return 0.0

        # Convert to hours and normalize (cap at 10 hours)
        hours_studied = progress.total_study_time / 3600
        return min(1.0, hours_studied / 10.0)

    async def _get_consistency_score(
        self, db: AsyncSession, user_id: uuid.UUID, topic_id: uuid.UUID
    ) -> float:
        """Get consistency score based on sessions in last 7 days (0-1)."""
        seven_days_ago = datetime.utcnow() - timedelta(days=7)

        query = select(func.count(StudySession.id)).where(
            StudySession.user_id == user_id,
            StudySession.topic_id == topic_id,
            StudySession.started_at >= seven_days_ago,
        )
        result = await db.execute(query)
        session_count = result.scalar()

        # Normalize (max 7 sessions in 7 days = 1.0)
        return min(1.0, session_count / 7.0)


# Singleton instance
progress_service = ProgressService()
