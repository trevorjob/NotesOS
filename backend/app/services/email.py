"""
NotesOS - Email Service
Transactional email via Resend.
"""

import resend
from app.config import settings


def _get_client() -> None:
    """Configure Resend SDK with the API key."""
    resend.api_key = settings.RESEND_API_KEY


async def send_password_reset_email(to: str, reset_url: str) -> None:
    """
    Send a password reset email.

    Args:
        to: Recipient email address
        reset_url: Full reset URL including token
    """
    _get_client()

    html_body = f"""
    <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
        <h2>Reset your NotesOS password</h2>
        <p>We received a request to reset the password for your account.</p>
        <p>Click the button below to set a new password. This link expires in <strong>1 hour</strong>.</p>
        <a href="{reset_url}"
           style="display:inline-block; padding:12px 24px; background:#4F46E5; color:#fff;
                  text-decoration:none; border-radius:6px; font-weight:bold;">
            Reset Password
        </a>
        <p style="margin-top:24px; color:#666; font-size:14px;">
            If you didn't request this, you can safely ignore this email.<br>
            The link will expire automatically.
        </p>
        <hr style="border:none; border-top:1px solid #eee; margin-top:32px;">
        <p style="color:#999; font-size:12px;">NotesOS — AI-powered study companion</p>
    </div>
    """

    resend.Emails.send({
        "from": settings.EMAIL_FROM,
        "to": [to],
        "subject": "Reset your NotesOS password",
        "html": html_body,
    })
