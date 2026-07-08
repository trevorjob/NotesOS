"""
Phase 3 — the emergent graph + discovery.

The contract under test:
- Classmates are exactly the people you share a course with, ranked by overlap.
- Discovery surfaces courses your classmates are in that you are not — but only
  once a course has *activity* (an upload, or a second member). Solo empty
  courses stay invisible.
- Discovery is notify-don't-enroll: seeing a course never joins you to it.
- The old public `join?search=` browse is gone.
"""


async def _create_course(client, headers, code="BIO201", name="Biology 201"):
    resp = await client.post(
        "/api/courses", headers=headers, json={"code": code, "name": name}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["course"]


async def _join(client, headers, course_id):
    resp = await client.post(
        "/api/courses/join", headers=headers, json={"course_id": course_id}
    )
    assert resp.status_code == 200, resp.text


async def _classmates(client, headers):
    resp = await client.get("/api/discovery/classmates", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["classmates"]


async def _discover(client, headers):
    resp = await client.get("/api/discovery/courses", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["courses"]


async def test_classmates_lists_shared_course_peers(client, register_user):
    a = await register_user()
    b = await register_user()
    course = await _create_course(client, a["headers"])
    await _join(client, b["headers"], course["id"])

    a_mates = await _classmates(client, a["headers"])
    assert [m["id"] for m in a_mates] == [b["id"]]
    assert a_mates[0]["shared_courses"] == 1

    # Symmetric — B sees A.
    b_mates = await _classmates(client, b["headers"])
    assert [m["id"] for m in b_mates] == [a["id"]]


async def test_non_overlapping_users_are_not_classmates(client, register_user):
    a = await register_user()
    b = await register_user()
    await _create_course(client, a["headers"], code="AAA")
    await _create_course(client, b["headers"], code="BBB")

    # No shared course ⇒ empty graph on both sides.
    assert await _classmates(client, a["headers"]) == []
    assert await _classmates(client, b["headers"]) == []


async def test_classmates_ranked_by_shared_count(client, register_user):
    a = await register_user()
    b = await register_user()
    c = await register_user()
    course1 = await _create_course(client, a["headers"], code="C1")
    course2 = await _create_course(client, a["headers"], code="C2")
    await _join(client, b["headers"], course1["id"])
    await _join(client, b["headers"], course2["id"])
    await _join(client, c["headers"], course1["id"])

    a_mates = await _classmates(client, a["headers"])
    # B shares 2 courses, C shares 1 — B ranks first.
    assert [(m["id"], m["shared_courses"]) for m in a_mates] == [
        (b["id"], 2),
        (c["id"], 1),
    ]


async def test_discovery_hides_solo_empty_course(client, register_user):
    a = await register_user()
    b = await register_user()
    shared = await _create_course(client, a["headers"], code="SHARED")
    await _join(client, b["headers"], shared["id"])

    # B spins up a private, empty course. It has one member and no uploads.
    await _create_course(client, b["headers"], code="SOLO", name="Solo Course")

    # A's classmate (B) is in it, but the activity gate keeps it out of discovery.
    assert await _discover(client, a["headers"]) == []


async def test_discovery_surfaces_active_classmate_course(client, register_user):
    a = await register_user()
    b = await register_user()
    c = await register_user()
    shared = await _create_course(client, a["headers"], code="SHARED")
    await _join(client, b["headers"], shared["id"])

    # B creates another course; a second member (C) makes it active.
    other = await _create_course(client, b["headers"], code="OTHER", name="Other Course")
    await _join(client, c["headers"], other["id"])

    discovered = await _discover(client, a["headers"])
    assert [d["course_id"] for d in discovered] == [other["id"]]
    assert discovered[0]["signals"]["classmates_here"] == 1  # only B is A's classmate
    assert discovered[0]["member_count"] == 2
    # A's own shared course is never in A's discovery feed.
    assert shared["id"] not in [d["course_id"] for d in discovered]


async def test_discovery_does_not_enroll(client, register_user):
    a = await register_user()
    b = await register_user()
    c = await register_user()
    shared = await _create_course(client, a["headers"], code="SHARED")
    await _join(client, b["headers"], shared["id"])
    other = await _create_course(client, b["headers"], code="OTHER")
    await _join(client, c["headers"], other["id"])

    # Seeing the course in discovery must not join A to it.
    discovered = await _discover(client, a["headers"])
    assert other["id"] in [d["course_id"] for d in discovered]

    listing = await client.get("/api/courses", headers=a["headers"])
    assert other["id"] not in [c["id"] for c in listing.json()["courses"]]


async def test_public_search_join_is_gone(client, register_user):
    a = await register_user()
    await _create_course(client, a["headers"], code="FINDME", name="Findable Course")

    b = await register_user()
    # The old public browse: a search term with no invite/course_id. The field no
    # longer exists, so this resolves to "no course specified" → 404, not a listing.
    resp = await client.post(
        "/api/courses/join", headers=b["headers"], json={"search": "Findable"}
    )
    assert resp.status_code == 404, resp.text
