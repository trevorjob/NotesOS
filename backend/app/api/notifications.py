"""
NotesOS API - Notifications Endpoints
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.api.auth import get_current_user

router = APIRouter()


@router.get("")
async def list_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all notifications for the current user, newest first."""
    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
    )
    notifications = result.scalars().all()

    return {
        "notifications": [
            {
                "id": str(n.id),
                "type": n.type.value,
                "title": n.title,
                "body": n.body,
                "is_read": n.is_read,
                "meta_data": n.meta_data,
                "created_at": n.created_at.isoformat(),
            }
            for n in notifications
        ]
    }


@router.patch("/read-all", status_code=status.HTTP_200_OK)
async def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all notifications as read for the current user."""
    await db.execute(
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True)
    )
    await db.commit()
    return {"message": "All notifications marked as read."}


@router.patch("/{notification_id}/read", status_code=status.HTTP_200_OK)
async def mark_notification_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a single notification as read (ownership enforced)."""
    result = await db.execute(
        select(Notification).where(Notification.id == uuid.UUID(notification_id))
    )
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found.")

    if notification.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")

    notification.is_read = True
    await db.commit()

    return {
        "id": str(notification.id),
        "is_read": notification.is_read,
    }
