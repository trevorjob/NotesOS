"""
NotesOS - Notification Service
Creates notification records and pushes real-time events via Redis pub/sub.
"""

import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification, NotificationType
from app.services.redis_client import redis_client


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

    Args:
        db: Active async DB session
        user_id: UUID of the target user
        notif_type: NotificationType enum value
        title: Short notification title
        body: Notification body text
        meta_data: Optional JSONB payload (e.g. test_id, course_id)

    Returns:
        The created Notification instance
    """
    notification = Notification(
        user_id=user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id)),
        type=notif_type,
        title=title,
        body=body,
        meta_data=meta_data,
    )
    db.add(notification)
    await db.commit()
    await db.refresh(notification)

    # Push via Redis so the WebSocket layer can forward it to the connected client
    try:
        await redis_client.publish(
            channel="user_notifications",
            message={
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
            },
        )
    except Exception as e:
        print(f"[NOTIFICATIONS] Failed to push via Redis: {e}")

    return notification
