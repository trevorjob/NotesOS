"""
NotesOS - Notification Service
Creates notification records and pushes real-time events via Redis pub/sub.
"""

import asyncio
import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationType
from app.services.redis_client import redis_client
from app.services.push import send_expo_push
from app.core.logging import get_logger

logger = get_logger(__name__)


async def create_and_push_notification(
    db: AsyncSession,
    user_id,
    notif_type: NotificationType,
    title: str,
    body: str,
    meta_data: Optional[dict] = None,
) -> Notification:
    """
    Create a Notification record in the DB and push it to the user's
    WebSocket connection via Redis pub/sub.
    """
    uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))

    notification = Notification(
        user_id=uid,
        type=notif_type,
        title=title,
        body=body,
        meta_data=meta_data,
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)

    payload = {
        "user_id": str(notification.user_id),
        "notification": {
            "id": str(notification.id),
            "type": notification.type.value,
            "title": notification.title,
            "body": notification.body,
            "is_read": notification.is_read,
            "meta_data": notification.meta_data,
            "created_at": notification.created_at.isoformat(),
        },
    }
    for attempt in range(2):
        try:
            await redis_client.publish(channel="user_notifications", message=payload)
            break
        except Exception:
            if attempt == 0:
                await asyncio.sleep(1)
            else:
                logger.error(
                    "Failed to push notification via Redis after retry",
                    exc_info=True,
                    extra={"notification_id": str(notification.id), "user_id": str(uid)},
                )

    try:
        # `type` rides alongside meta_data so the mobile tap handler can route an OS push
        # the same way it routes an in-app tap (routeForNotification switches on `type`).
        push_data = {**(meta_data or {}), "type": notification.type.value}
        await send_expo_push(db, user_id=uid, title=title, body=body, data=push_data)
    except Exception:
        logger.error(
            "Failed to send Expo push",
            exc_info=True,
            extra={"notification_id": str(notification.id), "user_id": str(uid)},
        )

    return notification
