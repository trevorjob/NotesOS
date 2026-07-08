"""
Phase 2 — the proximity check on course creation.

The contract under test:
- School is the hard filter: no school on the creator ⇒ no check ⇒ straight create.
- A near-match at the same school is *offered* (HTTP 200, nothing created), never
  forced. ``force=true`` forks anyway.
- People signals rank the offer: programme > entry_year > shared classmates.
- The offer is actionable end-to-end: the creator can join a match (merge).
"""

import uuid


async def _register(
    client,
    *,
    school_name=None,
    program=None,
    entry_year=None,
    full_name="Test User",
):
    """Register a fresh user with proximity signals, return tokens + headers."""
    email = f"user_{uuid.uuid4().hex[:10]}@test.dev"
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "password123",
            "full_name": full_name,
            "school_name": school_name,
            "program": program,
            "entry_year": entry_year,
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    return {
        "id": data["user"]["id"],
        "school_id": data["user"]["school_id"],
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
    }


async def _create(client, headers, *, code, name, force=False):
    return await client.post(
        "/api/courses",
        headers=headers,
        json={"code": code, "name": name, "force": force},
    )


UNILAG = "University of Lagos"
OAU = "Obafemi Awolowo University"


async def test_no_school_skips_proximity(client):
    """A creator with no school runs no check — even an identical course forks."""
    a = await _register(client)  # no school
    b = await _register(client)  # no school

    first = await _create(client, a["headers"], code="CHM101", name="Chemistry 101")
    assert first.status_code == 201, first.text

    second = await _create(client, b["headers"], code="CHM101", name="Chemistry 101")
    # No school scope ⇒ no candidates ⇒ straight create, not an offer.
    assert second.status_code == 201, second.text


async def test_first_course_at_school_always_creates(client):
    """Nothing to match against yet ⇒ the first course is created outright."""
    a = await _register(client, school_name=UNILAG)
    resp = await _create(client, a["headers"], code="CHM101", name="Chemistry 101")
    assert resp.status_code == 201, resp.text
    assert resp.json()["course"]["code"] == "CHM101"


async def test_same_school_offers_match(client):
    """A near-match at the same school is offered, and nothing is created."""
    a = await _register(client, school_name=UNILAG)
    await _create(client, a["headers"], code="CHM101", name="Chemistry 101")

    b = await _register(client, school_name=UNILAG)
    resp = await _create(client, b["headers"], code="CHM101", name="Chem 101")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["proximity_check"] is True
    assert len(body["matches"]) == 1
    assert body["matches"][0]["code"] == "CHM101"

    # The offer created nothing: B is enrolled in no courses.
    listing = await client.get("/api/courses", headers=b["headers"])
    assert listing.json()["courses"] == []


async def test_force_forks_despite_match(client):
    """force=true bypasses the offer and creates a separate course."""
    a = await _register(client, school_name=UNILAG)
    await _create(client, a["headers"], code="CHM101", name="Chemistry 101")

    b = await _register(client, school_name=UNILAG)
    resp = await _create(
        client, b["headers"], code="CHM101", name="Chemistry 101", force=True
    )
    assert resp.status_code == 201, resp.text

    listing = await client.get("/api/courses", headers=b["headers"])
    assert [c["code"] for c in listing.json()["courses"]] == ["CHM101"]


async def test_different_school_no_match(client):
    """School is a hard filter: an identical course at another school never matches."""
    a = await _register(client, school_name=UNILAG)
    await _create(client, a["headers"], code="CHM101", name="Chemistry 101")

    b = await _register(client, school_name=OAU)
    resp = await _create(client, b["headers"], code="CHM101", name="Chemistry 101")
    assert resp.status_code == 201, resp.text


async def test_program_overlap_ranks_first(client):
    """Among matches, the course whose members share your programme leads."""
    # Two separate "CHM101" courses at the same school, by different-programme owners.
    physics_owner = await _register(client, school_name=UNILAG, program="Physics")
    phys_course = await _create(
        client, physics_owner["headers"], code="CHM101", name="Chemistry 101"
    )
    chem_owner = await _register(client, school_name=UNILAG, program="Chemistry")
    chem_course = await _create(
        client, chem_owner["headers"], code="CHM101", name="Chemistry 101", force=True
    )

    # A chemistry student should be offered the chemistry-owned section first.
    student = await _register(client, school_name=UNILAG, program="Chemistry")
    resp = await _create(client, student["headers"], code="CHM101", name="Chemistry 101")
    assert resp.status_code == 200, resp.text
    matches = resp.json()["matches"]
    assert len(matches) == 2
    assert matches[0]["course_id"] == chem_course.json()["course"]["id"]
    assert matches[0]["signals"]["same_program"] == 1


async def test_offered_match_is_joinable(client):
    """The merge path works end-to-end: decline the fork, join the offered course."""
    a = await _register(client, school_name=UNILAG)
    created = await _create(client, a["headers"], code="CHM101", name="Chemistry 101")
    course_id = created.json()["course"]["id"]

    b = await _register(client, school_name=UNILAG)
    offer = await _create(client, b["headers"], code="CHM101", name="Chemistry 101")
    assert offer.status_code == 200
    offered_id = offer.json()["matches"][0]["course_id"]
    assert offered_id == course_id

    joined = await client.post(
        "/api/courses/join", headers=b["headers"], json={"course_id": offered_id}
    )
    assert joined.status_code == 200, joined.text

    listing = await client.get("/api/courses", headers=b["headers"])
    assert course_id in [c["id"] for c in listing.json()["courses"]]
    # Merged, not forked: the course has both members, one row each.
    assert listing.json()["courses"][0]["member_count"] == 2
