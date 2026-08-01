"""
NotesOS API - Notifications Endpoints
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func

from app.database import get_db
from app.models.notification import Notification, NotificationPreference, DeviceToken
from app.models.user import User
from app.api.auth import get_current_user

router = APIRouter()

VALID_PLATFORMS = {"ios", "android"}


class PreferenceUpdate(BaseModel):
    digest_enabled: bool | None = None
    recognition_enabled: bool | None = None


class DeviceRegistration(BaseModel):
    token: str
    platform: str


def _pref_response(pref: NotificationPreference) -> dict:
    return {
        "digest_enabled": pref.digest_enabled,
        "recognition_enabled": pref.recognition_enabled,
        "last_digest_at": pref.last_digest_at.isoformat() if pref.last_digest_at else None,
    }


async def _get_or_create_pref(db: AsyncSession, user_id: uuid.UUID) -> NotificationPreference:
    pref = await db.scalar(
        select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    )
    if pref is None:
        pref = NotificationPreference(user_id=user_id)
        db.add(pref)
        await db.commit()
        await db.refresh(pref)
    return pref


@router.get("/preferences")
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """The current user's notification preferences (both nudge loops are on by default)."""
    pref = await _get_or_create_pref(db, current_user.id)
    return _pref_response(pref)


@router.patch("/preferences")
async def update_preferences(
    body: PreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle which habit-loop nudges the user receives (§15.4). Partial update."""
    pref = await _get_or_create_pref(db, current_user.id)
    if body.digest_enabled is not None:
        pref.digest_enabled = body.digest_enabled
    if body.recognition_enabled is not None:
        pref.recognition_enabled = body.recognition_enabled
    await db.commit()
    await db.refresh(pref)
    return _pref_response(pref)


@router.post("/devices", status_code=status.HTTP_200_OK)
async def register_device(
    body: DeviceRegistration,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register (or move) an Expo push token for OS-level push.

    Upsert on ``token``: Expo issues one token per install, not per user, so a reinstall
    or a different user signing in on the same device just moves the existing row to the
    caller instead of erroring on the unique constraint.
    """
    if body.platform not in VALID_PLATFORMS:
        raise HTTPException(status_code=422, detail="platform must be 'ios' or 'android'.")

    device = await db.scalar(select(DeviceToken).where(DeviceToken.token == body.token))
    if device is None:
        device = DeviceToken(user_id=current_user.id, token=body.token, platform=body.platform)
        db.add(device)
    else:
        device.user_id = current_user.id
        device.platform = body.platform
    await db.commit()
    return {"message": "Device registered."}


@router.delete("/devices/{token}", status_code=status.HTTP_204_NO_CONTENT)
async def unregister_device(
    token: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unregister a device (sign-out, account delete) — ownership enforced."""
    await db.execute(
        delete(DeviceToken).where(DeviceToken.token == token, DeviceToken.user_id == current_user.id)
    )
    await db.commit()


@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return count of unread notifications for the current user."""
    result = await db.execute(
        select(func.count(Notification.id))
        .where(Notification.user_id == current_user.id, Notification.is_read.is_(False))
    )
    return {"count": result.scalar_one()}


@router.get("")
async def list_notifications(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return paginated notifications for the current user, newest first."""
    total_result = await db.execute(
        select(func.count(Notification.id))
        .where(Notification.user_id == current_user.id)
    )
    total = total_result.scalar_one()

    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .offset(offset)
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
        ],
        "total": total,
        "has_more": (offset + limit) < total,
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


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_notification(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a single notification (ownership enforced)."""
    result = await db.execute(
        select(Notification).where(Notification.id == uuid.UUID(notification_id))
    )
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found.")

    if notification.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied.")

    await db.delete(notification)
    await db.commit()


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete all notifications for the current user."""
    await db.execute(
        delete(Notification).where(Notification.user_id == current_user.id)
    )
    await db.commit()


