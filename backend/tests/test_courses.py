"""Baseline coverage for course creation / join / enrollment via the API."""


async def _create_course(client, headers, code="BIO201", name="Biology 201"):
    resp = await client.post(
        "/api/courses",
        headers=headers,
        json={"code": code, "name": name},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["course"]


async def test_create_course_auto_enrolls_creator(client, register_user):
    user = await register_user()
    course = await _create_course(client, user["headers"])
    assert course["code"] == "BIO201"

    listing = await client.get("/api/courses", headers=user["headers"])
    assert listing.status_code == 200
    codes = [c["code"] for c in listing.json()["courses"]]
    assert "BIO201" in codes


async def test_public_course_join_by_id(client, register_user):
    creator = await register_user()
    course = await _create_course(client, creator["headers"])

    joiner = await register_user()
    resp = await client.post(
        "/api/courses/join",
        headers=joiner["headers"],
        json={"course_id": course["id"]},
    )
    assert resp.status_code == 200, resp.text

    listing = await client.get("/api/courses", headers=joiner["headers"])
    assert course["id"] in [c["id"] for c in listing.json()["courses"]]


async def test_double_join_is_rejected(client, register_user):
    creator = await register_user()
    course = await _create_course(client, creator["headers"])
    joiner = await register_user()

    first = await client.post(
        "/api/courses/join", headers=joiner["headers"], json={"course_id": course["id"]}
    )
    assert first.status_code == 200
    second = await client.post(
        "/api/courses/join", headers=joiner["headers"], json={"course_id": course["id"]}
    )
    assert second.status_code == 400


async def test_join_by_invite_code(client, register_user):
    # Every course now has an invite code (no public/private distinction).
    creator = await register_user()
    course = await _create_course(client, creator["headers"])
    assert course["invite_code"]

    joiner = await register_user()
    resp = await client.post(
        "/api/courses/join",
        headers=joiner["headers"],
        json={"invite_code": course["invite_code"]},
    )
    assert resp.status_code == 200, resp.text
