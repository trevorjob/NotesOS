"""Auth surface — phone-primary identity with OTP verification (A0)."""

import pytest

from tests.conftest import unique_phone


async def test_register_returns_otp_pending_not_tokens(client):
    resp = await client.post(
        "/api/auth/register",
        json={"phone": unique_phone(), "password": "password123", "full_name": "New User"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["requires_otp"] is True
    assert body["phone"]
    # No tokens are handed out before the phone is verified.
    assert "access_token" not in body


async def test_verify_otp_issues_tokens(client, otp_codes):
    phone = unique_phone()
    reg = await client.post(
        "/api/auth/register",
        json={"phone": phone, "password": "password123", "full_name": "V"},
    )
    assert reg.status_code == 201, reg.text

    verify = await client.post(
        "/api/auth/verify-otp", json={"phone": phone, "code": otp_codes[phone]},
    )
    assert verify.status_code == 200, verify.text
    body = verify.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["phone"] == phone
    assert body["user"]["phone_verified"] is True


async def test_verify_otp_wrong_code_rejected(client, otp_codes):
    phone = unique_phone()
    await client.post(
        "/api/auth/register",
        json={"phone": phone, "password": "password123", "full_name": "V"},
    )
    verify = await client.post(
        "/api/auth/verify-otp", json={"phone": phone, "code": "000000"},
    )
    assert verify.status_code == 400


async def test_register_verified_duplicate_phone_rejected(client, register_user):
    user = await register_user()
    resp = await client.post(
        "/api/auth/register",
        json={"phone": user["phone"], "password": "password123", "full_name": "Dup"},
    )
    assert resp.status_code == 400


async def test_reregister_unverified_phone_allowed(client, otp_codes):
    """An unverified stale registration can be overwritten — a typo can't lock a number."""
    phone = unique_phone()
    first = await client.post(
        "/api/auth/register",
        json={"phone": phone, "password": "password123", "full_name": "First"},
    )
    assert first.status_code == 201
    # Re-register the same (still unverified) number — allowed, re-issues an OTP.
    second = await client.post(
        "/api/auth/register",
        json={"phone": phone, "password": "newpassword1", "full_name": "Second"},
    )
    assert second.status_code == 201, second.text
    verify = await client.post(
        "/api/auth/verify-otp", json={"phone": phone, "code": otp_codes[phone]},
    )
    assert verify.status_code == 200
    assert verify.json()["user"]["full_name"] == "Second"


async def test_login_success(client, register_user):
    user = await register_user(password="secretpw1")
    resp = await client.post(
        "/api/auth/login",
        json={"phone": user["phone"], "password": "secretpw1"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["access_token"]


async def test_login_wrong_password_rejected(client, register_user):
    user = await register_user(password="rightpw12")
    resp = await client.post(
        "/api/auth/login",
        json={"phone": user["phone"], "password": "notmypw12"},
    )
    assert resp.status_code == 401


async def test_login_unverified_phone_forbidden(client):
    phone = unique_phone()
    await client.post(
        "/api/auth/register",
        json={"phone": phone, "password": "password123", "full_name": "Unverified"},
    )
    resp = await client.post(
        "/api/auth/login", json={"phone": phone, "password": "password123"},
    )
    assert resp.status_code == 403


async def test_resend_otp_allows_verification(client, otp_codes):
    phone = unique_phone()
    await client.post(
        "/api/auth/register",
        json={"phone": phone, "password": "password123", "full_name": "R"},
    )
    otp_codes.pop(phone, None)
    resend = await client.post("/api/auth/otp/resend", json={"phone": phone})
    assert resend.status_code == 200
    assert phone in otp_codes  # a fresh code was issued
    verify = await client.post(
        "/api/auth/verify-otp", json={"phone": phone, "code": otp_codes[phone]},
    )
    assert verify.status_code == 200


async def test_refresh_issues_new_access_token(client, register_user):
    user = await register_user()
    resp = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": user["tokens"]["refresh_token"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["access_token"]


async def test_email_is_optional_and_stored(client, register_user):
    user = await register_user(email="opt@test.dev")
    me = await client.get("/api/auth/me", headers=user["headers"])
    assert me.status_code == 200
    assert me.json()["email"] == "opt@test.dev"


async def test_oauth_register_collects_and_verifies_phone(client, otp_codes):
    """A new Google identity must still enter + OTP-verify a phone (never inferred)."""
    from app.api.auth import create_oauth_register_token

    token = create_oauth_register_token(
        google_id="g-123", email="gmail@test.dev", name="G User", picture=None
    )
    phone = unique_phone()
    reg = await client.post(
        "/api/auth/oauth/register", json={"oauth_token": token, "phone": phone},
    )
    assert reg.status_code == 201, reg.text
    assert reg.json()["requires_otp"] is True

    verify = await client.post(
        "/api/auth/verify-otp", json={"phone": phone, "code": otp_codes[phone]},
    )
    assert verify.status_code == 200, verify.text
    user = verify.json()["user"]
    assert user["phone"] == phone
    assert user["phone_verified"] is True
    assert user["email"] == "gmail@test.dev"


async def test_oauth_register_rejects_bad_token(client):
    resp = await client.post(
        "/api/auth/oauth/register",
        json={"oauth_token": "not-a-real-token", "phone": unique_phone()},
    )
    assert resp.status_code == 400


async def test_protected_route_requires_auth(client):
    resp = await client.get("/api/courses")
    assert resp.status_code in (401, 403)
