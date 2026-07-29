"""
NotesOS API - Authentication Endpoints
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional
import uuid
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from jose import jwt, JWTError
from passlib.context import CryptContext
import httpx

from app.config import settings
from app.database import get_db
from app.models import User, RefreshToken
from app.services.phone import phone_hash as compute_phone_hash

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

router = APIRouter()
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# =============================================================================
# Schemas
# =============================================================================


class RegisterRequest(BaseModel):
    # Phone is the primary identity — required, password-based (no OTP).
    phone: str
    password: str
    full_name: str
    email: Optional[EmailStr] = None
    study_personality: Optional[dict] = None
    # Proximity-check signals — all optional (a US fresher may know none of them).
    school_name: Optional[str] = None
    program: Optional[str] = None
    entry_year: Optional[int] = None


class LoginRequest(BaseModel):
    phone: str
    password: str


class OAuthPhoneRequest(BaseModel):
    """Attaches a phone to a verified Google identity, completing sign-up."""
    oauth_token: str
    phone: str
    school_name: Optional[str] = None
    program: Optional[str] = None
    entry_year: Optional[int] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    phone: str
    email: Optional[str] = None
    full_name: str
    avatar_url: Optional[str] = None
    study_personality: Optional[dict] = None
    university: Optional[str] = None
    school_id: Optional[str] = None
    program: Optional[str] = None
    entry_year: Optional[int] = None


class PersonalityUpdate(BaseModel):
    tone: Optional[str] = None
    emoji_usage: Optional[str] = None
    explanation_style: Optional[str] = None


class LogoutRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class PreferencesUpdate(BaseModel):
    preferences: Optional[dict] = None
    personality_tags: Optional[list] = None


class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    university: Optional[str] = None
    school_name: Optional[str] = None
    program: Optional[str] = None
    entry_year: Optional[int] = None
    # Phone is the primary identity and is intentionally NOT editable here.


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class DeleteAccountRequest(BaseModel):
    # Reauth for password accounts; ignored (may be omitted) for OAuth-only accounts.
    password: Optional[str] = None


# =============================================================================
# Utility Functions
# =============================================================================


def serialize_user(user: User) -> dict:
    """Single source of truth for the user payload returned across auth endpoints."""
    return {
        "id": str(user.id),
        "phone": user.phone,
        "email": user.email,
        "full_name": user.full_name,
        "avatar_url": user.avatar_url,
        "study_personality": user.study_personality,
        "university": user.university,
        "school_id": str(user.school_id) if user.school_id else None,
        "program": user.program,
        "entry_year": user.entry_year,
    }


def normalize_phone(raw: str) -> str:
    """Trim and strip spaces/dashes/parens; preserve a leading '+'.

    Intentionally light — international formats vary and we don't want to reject
    a valid number. Just enough to keep the unique index from splitting on cosmetic
    differences.
    """
    stripped = (raw or "").strip()
    plus = stripped.startswith("+")
    digits = "".join(ch for ch in stripped if ch.isdigit())
    if not digits:
        return ""
    return ("+" if plus else "") + digits


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


OAUTH_REGISTER_PURPOSE = "oauth_register"


def create_oauth_register_token(google_id: str, email: str, name: str, picture: Optional[str]) -> str:
    """Short-lived token carrying a verified Google identity to the phone step."""
    expire = datetime.utcnow() + timedelta(
        minutes=settings.OAUTH_REGISTER_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "purpose": OAUTH_REGISTER_PURPOSE,
        "google_id": google_id,
        "email": email,
        "name": name,
        "picture": picture,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_oauth_register_token(token: str) -> dict:
    """Validate an oauth-register token; raise 400 on tamper/expiry/wrong purpose."""
    invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired OAuth registration token.",
    )
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
    except JWTError:
        raise invalid
    if payload.get("purpose") != OAUTH_REGISTER_PURPOSE:
        raise invalid
    return payload


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

    # A soft-deleted / deactivated account's still-valid access token must stop working
    # immediately (it has up to 15 min left), so gate every authenticated request here.
    if not user.is_active:
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


async def _resolve_school_id(db: AsyncSession, school_name: Optional[str]):
    """Canonicalise a typed school name to a row id (created if new)."""
    if not school_name:
        return None
    from app.services.school import find_or_create_school

    school = await find_or_create_school(db, school_name)
    return school.id if school else None


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    request: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user with phone + password. Issues tokens immediately."""
    phone_value = normalize_phone(request.phone)
    if not phone_value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid phone number is required.",
        )

    existing_phone = await db.execute(select(User).where(User.phone == phone_value))
    if existing_phone.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number already registered",
        )

    # Email is optional but unique-when-present.
    email_value = request.email or None
    if email_value:
        existing_email = await db.execute(select(User).where(User.email == email_value))
        if existing_email.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

    school_id = await _resolve_school_id(db, request.school_name)
    personality = request.study_personality or {
        "tone": "encouraging",
        "emoji_usage": "moderate",
        "explanation_style": "detailed",
    }

    user = User(
        phone=phone_value,
        phone_hash=compute_phone_hash(phone_value),
        email=email_value,
        password_hash=hash_password(request.password),
        full_name=request.full_name,
        study_personality=personality,
        school_id=school_id,
        program=request.program,
        entry_year=request.entry_year,
        last_login=datetime.utcnow(),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    if user.email:
        from app.services.email import send_welcome_email

        background_tasks.add_task(send_welcome_email, user.email, user.full_name)

    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = await create_refresh_token(user.id, db)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": serialize_user(user),
    }


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with phone and password."""
    phone_value = normalize_phone(request.phone)
    result = await db.execute(select(User).where(User.phone == phone_value))
    user = result.scalar_one_or_none()

    if (
        not user
        or not user.is_active
        or not user.password_hash
        or not verify_password(request.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect phone or password",
        )

    # Update last login; opportunistically backfill phone_hash for pre-existing
    # accounts created before contact-match shipped (self-heals as users log in).
    user.last_login = datetime.utcnow()
    if not user.phone_hash:
        user.phone_hash = compute_phone_hash(user.phone)
    await db.commit()

    # Generate tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = await create_refresh_token(user.id, db)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": serialize_user(user),
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

    if not user or not user.is_active:
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
        "user": serialize_user(user),
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
    return serialize_user(current_user)


@router.patch("/me/personality")
async def update_personality(
    prefs: PersonalityUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user's study personality preferences."""
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


@router.patch("/me")
async def update_profile(
    data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user profile fields (name, school, and proximity-check signals)."""
    if data.full_name is not None:
        current_user.full_name = data.full_name.strip()
    if data.university is not None:
        current_user.university = data.university.strip() or None
    if data.school_name is not None:
        from app.services.school import find_or_create_school

        school = await find_or_create_school(db, data.school_name)
        current_user.school_id = school.id if school else None
    if data.program is not None:
        current_user.program = data.program.strip() or None
    if data.entry_year is not None:
        current_user.entry_year = data.entry_year
    await db.commit()
    return serialize_user(current_user)


@router.post("/me/change-password", status_code=status.HTTP_200_OK)
async def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change password — verifies current password before updating."""
    if not current_user.password_hash:
        raise HTTPException(status_code=400, detail="Password change not available for OAuth accounts.")
    if not pwd_context.verify(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters.")
    current_user.password_hash = hash_password(data.new_password)
    await db.commit()
    return {"message": "Password updated successfully."}


@router.post("/me/delete", status_code=status.HTTP_200_OK)
async def delete_account(
    data: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete the current account: anonymise PII, free the phone, deactivate,
    revoke all sessions.

    Contributions (uploaded resources) are intentionally KEPT so shared course notes
    don't break for classmates — they simply show as "Former member". Password accounts
    must reauth with their current password; OAuth-only accounts (no password) skip it.
    """
    if current_user.password_hash:
        if not data.password or not pwd_context.verify(
            data.password, current_user.password_hash
        ):
            raise HTTPException(status_code=400, detail="Password is incorrect.")

    # Wipe PII / auth. Phone is NOT NULL + unique, so it takes a unique sentinel — which
    # also frees the real number for a fresh sign-up later.
    current_user.full_name = "Former member"
    current_user.email = None
    current_user.phone = f"deleted:{secrets.token_hex(10)}"
    current_user.phone_hash = None
    current_user.password_hash = None
    current_user.avatar_url = None
    current_user.google_id = None
    current_user.university = None
    current_user.program = None
    current_user.entry_year = None
    current_user.study_personality = None
    current_user.preferences = None
    current_user.personality_tags = None
    current_user.password_reset_token = None
    current_user.password_reset_expires = None
    current_user.is_active = False

    # Kill every session — the ≤15-min access token is separately blocked by the
    # is_active gate in get_current_user.
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == current_user.id)
        .values(is_revoked=True)
    )
    await db.commit()
    return {"message": "Your account has been deleted."}


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    request: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Initiate password reset flow.
    Always returns 200 to prevent email enumeration.
    """
    from app.services.email import send_password_reset_email

    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalar_one_or_none()

    if user:
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        user.password_reset_token = token_hash
        user.password_reset_expires = datetime.utcnow() + timedelta(hours=1)
        await db.commit()

        reset_url = f"{settings.PASSWORD_RESET_URL}?token={raw_token}"
        try:
            await send_password_reset_email(user.email, reset_url)
        except Exception:
            pass

    return {"message": "If that email exists, a reset link has been sent."}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reset user password using a valid reset token."""
    token_hash = hashlib.sha256(request.token.encode()).hexdigest()

    result = await db.execute(
        select(User).where(User.password_reset_token == token_hash)
    )
    user = result.scalar_one_or_none()

    if not user or not user.password_reset_expires:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token.",
        )

    if datetime.utcnow() > user.password_reset_expires:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token.",
        )

    user.password_hash = hash_password(request.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    await db.commit()

    return {"message": "Password updated successfully."}


@router.get("/google")
async def google_login():
    """Redirect user to Google OAuth consent screen."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth is not configured.",
        )

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    from urllib.parse import urlencode
    url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    return RedirectResponse(url=url)


@router.get("/google/callback")
async def google_callback(
    code: str,
    db: AsyncSession = Depends(get_db),
):
    """Handle Google OAuth callback. Returns JWT tokens."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Google OAuth is not configured.",
        )

    async with httpx.AsyncClient() as client:
        # Exchange code for tokens
        token_response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )
        if token_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to exchange authorization code.",
            )
        token_data = token_response.json()
        google_access_token = token_data.get("access_token")

        # Fetch user info from Google
        userinfo_response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {google_access_token}"},
        )
        if userinfo_response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to fetch Google user info.",
            )
        userinfo = userinfo_response.json()

    google_id: str = userinfo.get("sub")
    email: str = userinfo.get("email", "")
    full_name: str = userinfo.get("name", email)
    avatar_url: Optional[str] = userinfo.get("picture")

    if not google_id or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account missing required fields.",
        )

    # Existing user? Log them straight in. Match by google_id, then by email.
    user: Optional[User] = None
    result = await db.execute(select(User).where(User.google_id == google_id))
    user = result.scalar_one_or_none()

    if not user:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user:
            user.google_id = google_id
            if avatar_url and not user.avatar_url:
                user.avatar_url = avatar_url
            await db.commit()
            await db.refresh(user)

    if user:
        # Phone is the primary identity; a prior account somehow lacking one is
        # routed through phone collection rather than logging in.
        if not user.phone:
            return {
                "requires_phone": True,
                "oauth_token": create_oauth_register_token(
                    google_id, email, full_name, avatar_url
                ),
                "email": email,
                "full_name": full_name,
                "avatar_url": avatar_url,
            }
        user.last_login = datetime.utcnow()
        await db.commit()
        await db.refresh(user)
        access_token = create_access_token(data={"sub": str(user.id)})
        refresh_token = await create_refresh_token(user.id, db)
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": serialize_user(user),
        }

    # New identity — never infer a phone from Google. Hand back a short-lived
    # intent token; the client collects a phone and calls /oauth/register.
    return {
        "requires_phone": True,
        "oauth_token": create_oauth_register_token(
            google_id, email, full_name, avatar_url
        ),
        "email": email,
        "full_name": full_name,
        "avatar_url": avatar_url,
    }


@router.post(
    "/oauth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
async def oauth_register(request: OAuthPhoneRequest, db: AsyncSession = Depends(get_db)):
    """Attach a phone to a Google identity, completing sign-up. No OTP — issues
    tokens immediately."""
    intent = decode_oauth_register_token(request.oauth_token)
    google_id = intent["google_id"]
    email_value = intent.get("email") or None

    phone_value = normalize_phone(request.phone)
    if not phone_value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid phone number is required.",
        )

    existing_phone = await db.execute(select(User).where(User.phone == phone_value))
    if existing_phone.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number already registered",
        )

    # Reuse an existing (phone-less) account for this Google identity if pending.
    gid_res = await db.execute(select(User).where(User.google_id == google_id))
    user = gid_res.scalar_one_or_none()

    school_id = await _resolve_school_id(db, request.school_name)

    if user:
        user.phone = phone_value
        user.phone_hash = compute_phone_hash(phone_value)
        if request.program is not None:
            user.program = request.program
        if request.entry_year is not None:
            user.entry_year = request.entry_year
        if school_id is not None:
            user.school_id = school_id
    else:
        user = User(
            phone=phone_value,
            phone_hash=compute_phone_hash(phone_value),
            email=email_value,
            google_id=google_id,
            full_name=intent.get("name") or email_value or phone_value,
            avatar_url=intent.get("picture"),
            password_hash=None,
            school_id=school_id,
            program=request.program,
            entry_year=request.entry_year,
        )
        db.add(user)

    user.last_login = datetime.utcnow()
    await db.commit()
    await db.refresh(user)

    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = await create_refresh_token(user.id, db)
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": serialize_user(user),
    }


@router.patch("/me/preferences")
async def update_preferences(
    request: PreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user preferences and/or personality tags."""
    if request.preferences is not None:
        current_user.preferences = request.preferences
    if request.personality_tags is not None:
        current_user.personality_tags = request.personality_tags

    await db.commit()
    await db.refresh(current_user)

    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "avatar_url": current_user.avatar_url,
        "study_personality": current_user.study_personality,
        "preferences": current_user.preferences,
        "personality_tags": current_user.personality_tags,
    }
