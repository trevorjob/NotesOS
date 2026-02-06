"""
NotesOS API - Authentication Endpoints
"""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import jwt, JWTError
from passlib.context import CryptContext

from app.config import settings
from app.database import get_db
from app.models import User

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
    token: str
    user: dict


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


# =============================================================================
# Helpers
# =============================================================================


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


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

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


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

    # Generate token
    token = create_access_token(data={"sub": str(user.id)})

    return {
        "token": token,
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

    # Generate token
    token = create_access_token(data={"sub": str(user.id)})

    return {
        "token": token,
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "study_personality": user.study_personality,
        },
    }


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
    request: PersonalityUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update AI personality preferences."""
    personality = current_user.study_personality or {}

    if request.tone:
        personality["tone"] = request.tone
    if request.emoji_usage:
        personality["emoji_usage"] = request.emoji_usage
    if request.explanation_style:
        personality["explanation_style"] = request.explanation_style

    current_user.study_personality = personality
    await db.commit()

    return {"message": "Personality updated! 🎉", "study_personality": personality}
