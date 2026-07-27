"""Register/profile wiring for the proximity-check signals (Phase 1.2), phone-primary."""

from tests.conftest import unique_phone


async def test_register_with_new_school_sets_school_id(client, register_user):
    user = await register_user(
        school_name="University of Lagos",
        program="Computer Science",
        entry_year=2027,
    )
    me = await client.get("/api/auth/me", headers=user["headers"])
    assert me.status_code == 200, me.text
    body = me.json()
    assert body["school_id"]
    assert body["program"] == "Computer Science"
    assert body["entry_year"] == 2027


async def test_two_users_same_school_share_school_id(client, register_user):
    async def _school_id(school_name):
        u = await register_user(full_name="U", school_name=school_name)
        me = await client.get("/api/auth/me", headers=u["headers"])
        return me.json()["school_id"]

    first = await _school_id("University of Ibadan")
    # Different spelling must canonicalise to the SAME school row.
    second = await _school_id("  university  of ibadan ")
    assert first and second and first == second


async def test_register_without_school_is_allowed(client, register_user):
    user = await register_user(full_name="No School")
    me = await client.get("/api/auth/me", headers=user["headers"])
    assert me.status_code == 200, me.text
    assert me.json()["school_id"] is None


async def test_duplicate_phone_rejected(client, register_user):
    user = await register_user()
    resp = await client.post(
        "/api/auth/register",
        json={"phone": user["phone"], "password": "password123", "full_name": "Phone Two"},
    )
    assert resp.status_code == 400


async def test_duplicate_email_rejected(client, register_user):
    """Email is optional but unique-when-present."""
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


async def test_profile_update_sets_signals(client, register_user):
    user = await register_user()
    resp = await client.patch(
        "/api/auth/me",
        headers=user["headers"],
        json={"school_name": "Covenant University", "program": "Law", "entry_year": 2025},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["school_id"]
    assert body["program"] == "Law"
    assert body["entry_year"] == 2025
