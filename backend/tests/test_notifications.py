"""Notifications: feed endpoints, device registration, and the Expo push fan-out.

Push send is faked (monkeypatch on `app.services.push.httpx`, mirroring test_llm.py's
_FakeClient pattern) — no test ever calls the real Expo API.
"""

import uuid

import pytest
from sqlalchemy import select

from app.models.notification import DeviceToken, Notification, NotificationType
from app.services import push as push_service
from app.services.notifications import create_and_push_notification


# --------------------------------------------------------------------------- #
# Device registration
# --------------------------------------------------------------------------- #

async def test_register_device_creates_row(client, register_user, db_session):
    user = await register_user()
    resp = await client.post(
        "/api/notifications/devices",
        json={"token": "ExponentPushToken[aaa]", "platform": "ios"},
        headers=user["headers"],
    )
    assert resp.status_code == 200

    device = await db_session.scalar(
        select(DeviceToken).where(DeviceToken.token == "ExponentPushToken[aaa]")
    )
    assert device is not None
    assert str(device.user_id) == user["id"]
    assert device.platform == "ios"


async def test_register_device_rejects_invalid_platform(client, register_user):
    user = await register_user()
    resp = await client.post(
        "/api/notifications/devices",
        json={"token": "ExponentPushToken[bbb]", "platform": "windows"},
        headers=user["headers"],
    )
    assert resp.status_code == 422


async def test_register_device_moves_token_between_users(client, register_user, db_session):
    """A reinstall/different-account-on-same-device just moves the row (upsert on token)."""
    owner_a = await register_user()
    owner_b = await register_user()
    token = "ExponentPushToken[shared]"

    resp_a = await client.post(
        "/api/notifications/devices", json={"token": token, "platform": "android"}, headers=owner_a["headers"]
    )
    assert resp_a.status_code == 200

    resp_b = await client.post(
        "/api/notifications/devices", json={"token": token, "platform": "android"}, headers=owner_b["headers"]
    )
    assert resp_b.status_code == 200

    rows = (await db_session.execute(select(DeviceToken).where(DeviceToken.token == token))).scalars().all()
    assert len(rows) == 1
    assert str(rows[0].user_id) == owner_b["id"]


async def test_unregister_device_requires_ownership(client, register_user, db_session):
    owner = await register_user()
    other = await register_user()
    token = "ExponentPushToken[ccc]"
    await client.post("/api/notifications/devices", json={"token": token, "platform": "ios"}, headers=owner["headers"])

    # A different user's delete is a silent no-op (204), not an error — but the token survives.
    resp = await client.delete(f"/api/notifications/devices/{token}", headers=other["headers"])
    assert resp.status_code == 204
    assert await db_session.scalar(select(DeviceToken).where(DeviceToken.token == token)) is not None

    resp = await client.delete(f"/api/notifications/devices/{token}", headers=owner["headers"])
    assert resp.status_code == 204
    assert await db_session.scalar(select(DeviceToken).where(DeviceToken.token == token)) is None


# --------------------------------------------------------------------------- #
# Feed endpoints
# --------------------------------------------------------------------------- #

async def test_list_and_read_notifications(client, register_user, db_session):
    user = await register_user()
    await create_and_push_notification(
        db_session,
        user_id=user["id"],
        notif_type=NotificationType.GENERAL,
        title="Hello",
        body="World",
    )

    resp = await client.get("/api/notifications", headers=user["headers"])
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    notif_id = body["notifications"][0]["id"]
    assert body["notifications"][0]["is_read"] is False

    unread = await client.get("/api/notifications/unread-count", headers=user["headers"])
    assert unread.json()["count"] == 1

    mark = await client.patch(f"/api/notifications/{notif_id}/read", headers=user["headers"])
    assert mark.status_code == 200

    unread_after = await client.get("/api/notifications/unread-count", headers=user["headers"])
    assert unread_after.json()["count"] == 0


async def test_mark_notification_read_enforces_ownership(client, register_user, db_session):
    owner = await register_user()
    other = await register_user()
    notif = await create_and_push_notification(
        db_session, user_id=owner["id"], notif_type=NotificationType.GENERAL, title="t", body="b"
    )

    resp = await client.patch(f"/api/notifications/{notif.id}/read", headers=other["headers"])
    assert resp.status_code == 403


# --------------------------------------------------------------------------- #
# Expo push fan-out (Lane 2)
# --------------------------------------------------------------------------- #

class _FakeResponse:
    def __init__(self, tickets):
        self._tickets = tickets

    def raise_for_status(self):
        return None

    def json(self):
        return {"data": self._tickets}


class _FakeExpoClient:
    def __init__(self, tickets_by_call):
        self._tickets_by_call = tickets_by_call
        self.calls: list[list[dict]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json):
        self.calls.append(json)
        tickets = self._tickets_by_call[len(self.calls) - 1]
        return _FakeResponse(tickets)


async def test_push_sends_to_registered_device(client, register_user, db_session, monkeypatch):
    user = await register_user()
    await client.post(
        "/api/notifications/devices", json={"token": "ExponentPushToken[ok]", "platform": "ios"}, headers=user["headers"]
    )

    fake_client = _FakeExpoClient(tickets_by_call=[[{"status": "ok", "id": "receipt-1"}]])
    monkeypatch.setattr(push_service.httpx, "AsyncClient", lambda **kw: fake_client)

    await create_and_push_notification(
        db_session, user_id=user["id"], notif_type=NotificationType.GENERAL, title="Hi", body="There"
    )

    assert len(fake_client.calls) == 1
    [message] = fake_client.calls[0]
    assert message["to"] == "ExponentPushToken[ok]"
    assert message["title"] == "Hi"
    assert message["body"] == "There"


async def test_push_prunes_unregistered_device(client, register_user, db_session, monkeypatch):
    user = await register_user()
    await client.post(
        "/api/notifications/devices", json={"token": "ExponentPushToken[dead]", "platform": "ios"}, headers=user["headers"]
    )

    fake_client = _FakeExpoClient(
        tickets_by_call=[[{"status": "error", "message": "gone", "details": {"error": "DeviceNotRegistered"}}]]
    )
    monkeypatch.setattr(push_service.httpx, "AsyncClient", lambda **kw: fake_client)

    await create_and_push_notification(
        db_session, user_id=user["id"], notif_type=NotificationType.GENERAL, title="Hi", body="There"
    )

    remaining = await db_session.scalar(
        select(DeviceToken).where(DeviceToken.token == "ExponentPushToken[dead]")
    )
    assert remaining is None


async def test_push_disabled_flag_skips_network_call(client, register_user, db_session, monkeypatch):
    user = await register_user()
    await client.post(
        "/api/notifications/devices", json={"token": "ExponentPushToken[flagged]", "platform": "ios"}, headers=user["headers"]
    )
    monkeypatch.setattr(push_service.settings, "ENABLE_PUSH", False, raising=False)

    called = False

    def _blow_up(**kw):
        nonlocal called
        called = True
        raise AssertionError("should not construct an httpx client when push is disabled")

    monkeypatch.setattr(push_service.httpx, "AsyncClient", _blow_up)

    await create_and_push_notification(
        db_session, user_id=user["id"], notif_type=NotificationType.GENERAL, title="Hi", body="There"
    )
    assert called is False


async def test_push_failure_does_not_break_notification_creation(client, register_user, db_session, monkeypatch):
    """A dead Expo API must never take down the in-app notification write."""
    user = await register_user()
    await client.post(
        "/api/notifications/devices", json={"token": "ExponentPushToken[flaky]", "platform": "ios"}, headers=user["headers"]
    )

    class _ExplodingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, *a, **kw):
            raise RuntimeError("network is down")

    monkeypatch.setattr(push_service.httpx, "AsyncClient", lambda **kw: _ExplodingClient())

    notif = await create_and_push_notification(
        db_session, user_id=user["id"], notif_type=NotificationType.GENERAL, title="Hi", body="There"
    )
    assert notif.id is not None
    stored = await db_session.scalar(select(Notification).where(Notification.id == notif.id))
    assert stored is not None
