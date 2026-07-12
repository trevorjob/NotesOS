"""
Enrollment integrity — the classmate graph is computed from course_enrollments,
so a user must appear at most once per course.

`test_duplicate_enrollment_rejected` is written RED against Phase 0.2: today the
model carries no unique constraint, so the duplicate commits silently and the
test fails. Adding UniqueConstraint(user_id, course_id) to the model turns it
GREEN (and the accompanying Alembic migration enforces it on the real database).
"""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Course, CourseEnrollment, User
from app.api.auth import hash_password
from tests.conftest import unique_phone


async def _seed_user_and_course(session):
    user = User(
        email=f"enr_{uuid.uuid4().hex[:10]}@test.dev",
        full_name="Enrolment Tester",
        password_hash=hash_password("password123"),
        phone=unique_phone(),
    )
    session.add(user)
    await session.flush()

    course = Course(code="ENR101", name="Enrolment 101", created_by=user.id)
    session.add(course)
    await session.flush()
    return user, course


async def test_duplicate_enrollment_rejected(db_session):
    user, course = await _seed_user_and_course(db_session)

    db_session.add(CourseEnrollment(user_id=user.id, course_id=course.id))
    await db_session.commit()

    db_session.add(CourseEnrollment(user_id=user.id, course_id=course.id))
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_same_course_different_users_allowed(db_session):
    user_a, course = await _seed_user_and_course(db_session)
    user_b = User(
        email=f"enr_{uuid.uuid4().hex[:10]}@test.dev",
        full_name="Second Tester",
        password_hash=hash_password("password123"),
        phone=unique_phone(),
    )
    db_session.add(user_b)
    await db_session.flush()

    db_session.add(CourseEnrollment(user_id=user_a.id, course_id=course.id))
    db_session.add(CourseEnrollment(user_id=user_b.id, course_id=course.id))
    await db_session.commit()  # must not raise


async def test_same_user_different_courses_allowed(db_session):
    user, course_a = await _seed_user_and_course(db_session)
    course_b = Course(code="ENR102", name="Enrolment 102", created_by=user.id)
    db_session.add(course_b)
    await db_session.flush()

    db_session.add(CourseEnrollment(user_id=user.id, course_id=course_a.id))
    db_session.add(CourseEnrollment(user_id=user.id, course_id=course_b.id))
    await db_session.commit()  # must not raise
