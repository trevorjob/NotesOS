"""
NotesOS - OS Push Service (Expo)

Lane 2 of the notification system (notifications-plan.md §2): reach the user when the
app is backgrounded/killed, where the WebSocket lane (services/notifications.py) can't.
Called from create_and_push_notification after the DB write + Redis publish, so every
existing and future emitter gets both lanes for free with no call-site changes.
"""

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.models.notification import DeviceToken

logger = get_logger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
EXPO_CHUNK_SIZE = 100  # Expo's per-request message cap.


async def send_expo_push(
    db: AsyncSession,
    *,
    user_id,
    title: str,
    body: str,
    data: dict | None = None,
) -> None:
    """Push a notification to every device registered for a user, via Expo's push API.

    Best-effort: swallows transport errors (a push failure must never break the DB write
    that already happened). Prunes tokens Expo reports as no-longer-registered.
    """
    if not settings.ENABLE_PUSH:
        return

    tokens = (
        await db.execute(select(DeviceToken.token).where(DeviceToken.user_id == user_id))
    ).scalars().all()
    if not tokens:
        return

    dead_tokens: list[str] = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for start in range(0, len(tokens), EXPO_CHUNK_SIZE):
            chunk = tokens[start : start + EXPO_CHUNK_SIZE]
            messages = [
                {"to": token, "title": title, "body": body, "data": data or {}, "sound": "default"}
                for token in chunk
            ]
            try:
                response = await client.post(EXPO_PUSH_URL, json=messages)
                response.raise_for_status()
            except Exception:
                logger.warning("push: Expo send failed for a chunk", exc_info=True)
                continue

            for token, ticket in zip(chunk, response.json().get("data", [])):
                if ticket.get("details", {}).get("error") == "DeviceNotRegistered":
                    dead_tokens.append(token)

    if dead_tokens:
        await db.execute(delete(DeviceToken).where(DeviceToken.token.in_(dead_tokens)))
        await db.commit()
