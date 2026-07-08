"""Register/profile wiring for the proximity-check signals (Phase 1.2)."""

import uuid


async def test_register_with_new_school_sets_school_id(client):
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": f"s_{uuid.uuid4().hex[:8]}@test.dev",
            "password": "password123",
            "full_name": "Signal User",
            "school_name": "University of Lagos",
            "program": "Computer Science",
            "entry_year": 2027,
        },
    )
    assert resp.status_code == 201, resp.text
    user = resp.json()["user"]
    assert user["school_id"]
    assert user["program"] == "Computer Science"
    assert user["entry_year"] == 2027


async def test_two_users_same_school_share_school_id(client):
    async def _register(school_name):
        r = await client.post(
            "/api/auth/register",
            json={
                "email": f"s_{uuid.uuid4().hex[:8]}@test.dev",
                "password": "password123",
                "full_name": "U",
                "school_name": school_name,
            },
        )
        assert r.status_code == 201, r.text
        return r.json()["user"]["school_id"]

    first = await _register("University of Ibadan")
    # Different spelling must canonicalise to the SAME school row.
    second = await _register("  university  of ibadan ")
    assert first and second and first == second


async def test_register_without_school_is_allowed(client):
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": f"s_{uuid.uuid4().hex[:8]}@test.dev",
            "password": "password123",
            "full_name": "No School",
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["user"]["school_id"] is None


async def test_duplicate_phone_rejected(client):
    phone = "+2348012345678"
    first = await client.post(
        "/api/auth/register",
        json={
            "email": f"s_{uuid.uuid4().hex[:8]}@test.dev",
            "password": "password123",
            "full_name": "Phone One",
            "phone": phone,
        },
    )
    assert first.status_code == 201, first.text

    second = await client.post(
        "/api/auth/register",
        json={
            "email": f"s_{uuid.uuid4().hex[:8]}@test.dev",
            "password": "password123",
            "full_name": "Phone Two",
            "phone": phone,
        },
    )
    assert second.status_code == 400


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
