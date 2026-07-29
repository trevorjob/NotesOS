"""Auth surface — phone-primary identity, password-based, no OTP."""

from tests.conftest import unique_phone


async def test_register_issues_tokens_immediately(client):
    resp = await client.post(
        "/api/auth/register",
        json={"phone": unique_phone(), "password": "password123", "full_name": "New User"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user"]["full_name"] == "New User"


async def test_register_duplicate_phone_rejected(client, register_user):
    user = await register_user()
    resp = await client.post(
        "/api/auth/register",
        json={"phone": user["phone"], "password": "password123", "full_name": "Dup"},
    )
    assert resp.status_code == 400


async def test_register_email_is_optional_and_stored(client):
    resp = await client.post(
        "/api/auth/register",
        json={
            "phone": unique_phone(),
            "password": "password123",
            "full_name": "V",
            "email": "opt@test.dev",
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["user"]["email"] == "opt@test.dev"


async def test_register_duplicate_email_rejected(client, register_user):
    await register_user(email="taken@test.dev")
    resp = await client.post(
        "/api/auth/register",
        json={
            "phone": unique_phone(),
            "password": "password123",
            "full_name": "Email Two",
            "email": "taken@test.dev",
        },
    )
    assert resp.status_code == 400


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


async def test_login_unknown_phone_rejected(client):
    resp = await client.post(
        "/api/auth/login",
        json={"phone": unique_phone(), "password": "password123"},
    )
    assert resp.status_code == 401


async def test_refresh_issues_new_access_token(client, register_user):
    user = await register_user()
    resp = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": user["tokens"]["refresh_token"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["access_token"]


async def test_oauth_register_attaches_phone_and_issues_tokens(client):
    """A new Google identity attaches a phone and gets tokens immediately (no OTP)."""
    from app.api.auth import create_oauth_register_token

    token = create_oauth_register_token(
        google_id="g-123", email="gmail@test.dev", name="G User", picture=None
    )
    resp = await client.post(
        "/api/auth/oauth/register",
        json={"oauth_token": token, "phone": unique_phone()},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["access_token"]
    assert body["user"]["email"] == "gmail@test.dev"


async def test_oauth_register_rejects_bad_token(client):
    resp = await client.post(
        "/api/auth/oauth/register",
        json={"oauth_token": "not-a-real-token", "phone": unique_phone()},
    )
    assert resp.status_code == 400


async def test_protected_route_requires_auth(client):
    resp = await client.get("/api/courses")
    assert resp.status_code in (401, 403)


# ── Account deletion (soft-delete + anonymise) ───────────────────────────────────


async def test_delete_account_requires_correct_password(client, register_user):
    """A password account must reauth; a wrong password leaves it untouched."""
    user = await register_user(password="password123")
    resp = await client.post(
        "/api/auth/me/delete", json={"password": "wrong"}, headers=user["headers"]
    )
    assert resp.status_code == 400, resp.text
    # Still usable — the account was not deleted.
    me = await client.get("/api/auth/me", headers=user["headers"])
    assert me.status_code == 200


async def test_delete_account_locks_out_and_revokes(client, register_user):
    """After delete: the live access token is rejected and the refresh token is dead."""
    user = await register_user(password="password123")

    resp = await client.post(
        "/api/auth/me/delete", json={"password": "password123"}, headers=user["headers"]
    )
    assert resp.status_code == 200, resp.text

    # The still-unexpired access token must now be rejected (is_active gate).
    me = await client.get("/api/auth/me", headers=user["headers"])
    assert me.status_code == 401

    # The refresh token must no longer mint new access tokens.
    refreshed = await client.post(
        "/api/auth/refresh", json={"refresh_token": user["tokens"]["refresh_token"]}
    )
    assert refreshed.status_code == 401


async def test_delete_account_frees_phone_for_reregistration(client, register_user):
    """The deleted account's phone is released, so the number can sign up fresh."""
    user = await register_user(phone=unique_phone(), password="password123")
    resp = await client.post(
        "/api/auth/me/delete", json={"password": "password123"}, headers=user["headers"]
    )
    assert resp.status_code == 200, resp.text

    # Old credentials no longer log in.
    login = await client.post(
        "/api/auth/login", json={"phone": user["phone"], "password": "password123"}
    )
    assert login.status_code == 401

    # The same number can register a brand-new account.
    again = await client.post(
        "/api/auth/register",
        json={"phone": user["phone"], "password": "newpass123", "full_name": "Fresh Start"},
    )
    assert again.status_code == 201, again.text


async def test_delete_account_anonymises_pii(client, register_user, db_session):
    """PII is wiped and the account is deactivated (contributions are kept elsewhere)."""
    import uuid as _uuid
    from sqlalchemy import select
    from app.models import User

    user = await register_user(password="password123", email="ada@test.dev")
    resp = await client.post(
        "/api/auth/me/delete", json={"password": "password123"}, headers=user["headers"]
    )
    assert resp.status_code == 200, resp.text

    row = await db_session.scalar(select(User).where(User.id == _uuid.UUID(user["id"])))
    assert row is not None
    assert row.is_active is False
    assert row.full_name == "Former member"
    assert row.email is None
    assert row.password_hash is None
    assert row.phone_hash is None
    assert row.phone != user["phone"]
    assert row.phone.startswith("deleted:")
