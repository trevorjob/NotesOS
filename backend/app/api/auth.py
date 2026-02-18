"""
NotesOS API - Authentication Endpoints
"""

import hashlib
from datetime import datetime, timedelta
from typing import Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import jwt, JWTError
from passlib.context import CryptContext

from app.config import settings
from app.database import get_db
from app.models import User, RefreshToken

router = APIRouter()
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# =============================================================================
# Schemas
# =============================================================================


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    study_personality: Optional[dict] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    avatar_url: Optional[str]
    study_personality: Optional[dict]


class PersonalityUpdate(BaseModel):
    tone: Optional[str] = None
    emoji_usage: Optional[str] = None
    explanation_style: Optional[str] = None


class LogoutRequest(BaseModel):
    refresh_token: str


# =============================================================================
# Utility Functions
# =============================================================================


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
    # return pwd_context.verify(_pre_hash_password(plain_password), hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


async def create_refresh_token(user_id: uuid.UUID, db: AsyncSession) -> str:
    """Create a new refresh token for the user."""
    # Generate unique token
    token_data = f"{user_id}{datetime.utcnow().isoformat()}{uuid.uuid4()}"
    token = hashlib.sha256(token_data.encode()).hexdigest()

    # Create refresh token record
    refresh_token = RefreshToken(
        token=token,
        user_id=user_id,
        expires_at=datetime.utcnow() + timedelta(days=30),  # 30 days
    )
    db.add(refresh_token)
    await db.commit()

    return token


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency to get current authenticated user."""
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    return user


async def verify_course_enrollment(
    db: AsyncSession, user_id: uuid.UUID, course_id: uuid.UUID
) -> None:
    """
    Verify that user is enrolled in course.
    Raises HTTPException if not enrolled.
    """
    from app.models.course import CourseEnrollment

    query = select(CourseEnrollment).where(
        CourseEnrollment.user_id == user_id, CourseEnrollment.course_id == course_id
    )
    result = await db.execute(query)
    enrollment = result.scalar_one_or_none()

    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enrolled in this course"
        )


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user account."""
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == request.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Create user
    user = User(
        email=request.email,
        password_hash=hash_password(request.password),
        full_name=request.full_name,
        study_personality=request.study_personality
        or {
            "tone": "encouraging",
            "emoji_usage": "moderate",
            "explanation_style": "detailed",
        },
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Generate tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = await create_refresh_token(user.id, db)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "study_personality": user.study_personality,
        },
    }


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with email and password."""
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()

    # Generate tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = await create_refresh_token(user.id, db)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "study_personality": user.study_personality,
        },
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(
    request: RefreshRequest, db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token."""
    # Find refresh token
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token == request.refresh_token)
    )
    refresh_token_record = result.scalar_one_or_none()

    if not refresh_token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Check if token is valid
    if not refresh_token_record.is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired or revoked",
        )

    # Get user
    result = await db.execute(
        select(User).where(User.id == refresh_token_record.user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Generate new tokens
    new_access_token = create_access_token(data={"sub": str(user.id)})
    new_refresh_token = await create_refresh_token(user.id, db)

    # Revoke old refresh token
    refresh_token_record.is_revoked = True
    await db.commit()

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "study_personality": user.study_personality,
        },
    }


@router.post("/logout")
async def logout(
    request: LogoutRequest,
    db: AsyncSession = Depends(get_db),
):
    """Revoke the refresh token. Client should clear tokens locally regardless."""
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.token == request.refresh_token)
    )
    refresh_token_record = result.scalar_one_or_none()
    if refresh_token_record:
        refresh_token_record.is_revoked = True
        await db.commit()
    return {"message": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user profile."""
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "avatar_url": current_user.avatar_url,
        "study_personality": current_user.study_personality,
    }


@router.patch("/me/personality")
async def update_personality(
    prefs: PersonalityUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user's study personality preferences."""
    # Update personality
    current_personality = current_user.study_personality or {}
    if prefs.tone:
        current_personality["tone"] = prefs.tone
    if prefs.emoji_usage:
        current_personality["emoji_usage"] = prefs.emoji_usage
    if prefs.explanation_style:
        current_personality["explanation_style"] = prefs.explanation_style

    current_user.study_personality = current_personality
    await db.commit()

    return {"study_personality": current_personality}
