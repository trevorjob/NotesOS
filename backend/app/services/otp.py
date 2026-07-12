"""
NotesOS - One-Time Password (OTP) service for phone verification.

Phone is the primary identity, verified by a short numeric code delivered over a
swappable channel (the owner picks WhatsApp vs SMS later). Everything provider-
specific lives behind ``send_otp`` — the single seam tests stub/capture, and the
only place a real delivery integration is wired in.

Storage of the pending challenge is NOT here: the hashed code + expiry live on the
User row (mirrors the password-reset pattern), so no extra table and no Redis
dependency for a flow that must work during registration before any session exists.
"""

import hashlib
import secrets
from datetime import datetime, timedelta

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

OTP_LENGTH = 6


def generate_code() -> str:
    """A zero-padded numeric OTP of ``OTP_LENGTH`` digits."""
    upper = 10**OTP_LENGTH
    return str(secrets.randbelow(upper)).zfill(OTP_LENGTH)


def hash_code(code: str) -> str:
    """Hash an OTP for at-rest storage — never persist the raw code."""
    return hashlib.sha256(code.encode()).hexdigest()


def code_expiry() -> datetime:
    """Expiry timestamp for a freshly issued code."""
    return datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)


def verify_code(code: str, stored_hash: str | None, expires_at: datetime | None) -> bool:
    """True only when the code matches an unexpired stored challenge."""
    if not stored_hash or not expires_at:
        return False
    if datetime.utcnow() > expires_at:
        return False
    return secrets.compare_digest(hash_code(code), stored_hash)


async def _send_console(phone: str, code: str) -> None:
    """Dev/test provider: log the code instead of delivering it."""
    logger.info("OTP for %s: %s (console provider)", phone, code)


async def send_otp(phone: str, code: str) -> None:
    """Deliver an OTP over the configured provider.

    Providers are swappable via ``OTP_PROVIDER``; only ``console`` ships today.
    WhatsApp/SMS integrations register here without touching any call site. Tests
    monkeypatch this function to capture the code.
    """
    provider = (settings.OTP_PROVIDER or "console").lower()
    if provider == "console":
        await _send_console(phone, code)
        return
    # Unknown provider configured but not yet implemented — fail loud rather than
    # silently dropping a verification code.
    raise NotImplementedError(f"OTP provider '{provider}' is not implemented")
