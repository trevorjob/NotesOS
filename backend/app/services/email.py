"""
NotesOS - Email Service
Transactional email via Resend.
Only used for: password reset and welcome on registration.
"""

import asyncio
import resend
from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_BASE_STYLE = """
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            max-width: 600px; margin: 0 auto; background: #F5F3EE; padding: 32px 24px;
            border-radius: 12px; color: #1C1A17;">
    <div style="margin-bottom: 24px;">
        <span style="font-size: 22px; font-weight: 700; letter-spacing: -0.5px;">NotesOS</span>
    </div>
    {content}
    <hr style="border: none; border-top: 1px solid #D6CFC3; margin: 32px 0;">
    <p style="color: #8C7B6B; font-size: 12px; margin: 0;">NotesOS — AI-powered study companion</p>
</div>
"""


def _wrap(content: str) -> str:
    return _BASE_STYLE.format(content=content)


def _send_sync(to: str, subject: str, html: str) -> None:
    resend.api_key = settings.RESEND_API_KEY
    try:
        resend.Emails.send({"from": settings.EMAIL_FROM, "to": [to], "subject": subject, "html": html})
    except Exception:
        logger.error("Failed to send email via Resend", exc_info=True, extra={"to": to, "subject": subject})


async def _send(to: str, subject: str, html: str) -> None:
    await asyncio.to_thread(_send_sync, to, subject, html)


async def send_welcome_email(to: str, full_name: str) -> None:
    first = full_name.split()[0] if full_name else "there"
    content = f"""
        <h2 style="margin: 0 0 16px; font-size: 20px;">Welcome to NotesOS, {first}!</h2>
        <p style="color: #4A3728; margin: 0 0 16px;">
            Your AI-powered study companion is ready. Upload your notes, generate quizzes,
            and let the AI tutor help you actually understand your material — not just collect it.
        </p>
        <p style="color: #4A3728; margin: 0 0 24px;">Get started by creating your first course.</p>
        <a href="{settings.PASSWORD_RESET_URL.replace('/reset-password', '/home')}"
           style="display:inline-block; padding:12px 24px; background:#D97706; color:#fff;
                  text-decoration:none; border-radius:8px; font-weight:600; font-size:15px;">
            Go to NotesOS
        </a>
    """
    await _send(to, "Welcome to NotesOS", _wrap(content))


async def send_password_reset_email(to: str, reset_url: str) -> None:
    content = f"""
        <h2 style="margin: 0 0 16px; font-size: 20px;">Reset your password</h2>
        <p style="color: #4A3728; margin: 0 0 24px;">
            We received a request to reset the password for your account.
            Click below to set a new password — this link expires in <strong>1 hour</strong>.
        </p>
        <a href="{reset_url}"
           style="display:inline-block; padding:12px 24px; background:#D97706; color:#fff;
                  text-decoration:none; border-radius:8px; font-weight:600; font-size:15px;">
            Reset Password
        </a>
        <p style="margin-top: 24px; color: #8C7B6B; font-size: 13px;">
            If you didn't request this, you can safely ignore this email.
        </p>
    """
    await _send(to, "Reset your NotesOS password", _wrap(content))
