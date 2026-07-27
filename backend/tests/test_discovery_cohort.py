"""
Cohort discovery — the enrollment-independent surface a brand-new user sees first.

The contract under test (see docs/mobile-integration-plan.md §6):
- Cohort = people at *your school* who share *your program* and *your entry_year*
  (each signal is a hard filter only when you actually have it).
- It surfaces the **active** courses your cohort is in that you are not — with NO
  shared-enrollment required. This is what makes it useful at onboarding, when you
  have joined nothing yet (classmate-discovery is empty then).
- Same activity gate as classmate-discovery: a solo, empty course stays invisible.
- Notify-don't-enroll: seeing a cohort course never joins you to it.
- No school ⇒ no cohort ⇒ empty (nothing to scope against).
"""

# A shared school string → shared school_id (canonicalised server-side at register).
SCHOOL = "University of Lagos"


async def _register(register_user, *, program=None, entry_year=None, school=SCHOOL):
    return await register_user(school_name=school, program=program, entry_year=entry_year)


async def _create_course(client, headers, code="BIO201", name=None):
    # force=True skips the proximity check — these tests exercise cohort discovery,
    # not the offer-or-fork flow, so every create must actually create. Name defaults
    # off the code to keep courses distinct.
    resp = await client.post(
        "/api/courses",
        headers=headers,
        json={"code": code, "name": name or f"{code} Course", "force": True},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["course"]


async def _join(client, headers, course_id):
    resp = await client.post(
        "/api/courses/join", headers=headers, json={"course_id": course_id}
    )
    assert resp.status_code == 200, resp.text


async def _cohort(client, headers):
    resp = await client.get("/api/discovery/cohort", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["courses"]


async def test_cohort_surfaces_active_course_of_a_peer_with_no_shared_enrollment(
    client, register_user
):
    """The key behaviour: a fresh user (zero enrollments) still sees their cohort's
    active courses. Classmate-discovery would be empty here."""
    me = await _register(register_user, program="Biology", entry_year=2025)
    peer = await _register(register_user, program="Biology", entry_year=2025)
    other = await _register(register_user, program="Biology", entry_year=2025)

    # Peer spins up a course; a second member makes it active. `me` is in nothing.
    course = await _create_course(client, peer["headers"], code="CHEM101")
    await _join(client, other["headers"], course["id"])

    discovered = await _cohort(client, me["headers"])
    assert [d["course_id"] for d in discovered] == [course["id"]]
    # Both peer and other are in my cohort and in the course.
    assert discovered[0]["signals"]["cohort_peers_here"] == 2
    assert discovered[0]["member_count"] == 2


async def test_cohort_respects_activity_gate(client, register_user):
    me = await _register(register_user, program="Biology", entry_year=2025)
    peer = await _register(register_user, program="Biology", entry_year=2025)

    # Peer's solo, empty course — one member, no uploads. Stays invisible.
    await _create_course(client, peer["headers"], code="SOLO", name="Solo Course")

    assert await _cohort(client, me["headers"]) == []


async def test_cohort_excludes_different_program(client, register_user):
    me = await _register(register_user, program="Biology", entry_year=2025)
    phys1 = await _register(register_user, program="Physics", entry_year=2025)
    phys2 = await _register(register_user, program="Physics", entry_year=2025)

    course = await _create_course(client, phys1["headers"], code="PHYS101")
    await _join(client, phys2["headers"], course["id"])  # active, but Physics-only

    assert await _cohort(client, me["headers"]) == []


async def test_cohort_excludes_different_entry_year(client, register_user):
    me = await _register(register_user, program="Biology", entry_year=2025)
    senior1 = await _register(register_user, program="Biology", entry_year=2023)
    senior2 = await _register(register_user, program="Biology", entry_year=2023)

    course = await _create_course(client, senior1["headers"], code="BIO301")
    await _join(client, senior2["headers"], course["id"])

    assert await _cohort(client, me["headers"]) == []


async def test_cohort_excludes_different_school(client, register_user):
    me = await _register(register_user, program="Biology", entry_year=2025, school="University of Lagos")
    away1 = await _register(register_user, program="Biology", entry_year=2025, school="University of Ibadan")
    away2 = await _register(register_user, program="Biology", entry_year=2025, school="University of Ibadan")

    course = await _create_course(client, away1["headers"], code="BIO201")
    await _join(client, away2["headers"], course["id"])

    assert await _cohort(client, me["headers"]) == []


async def test_cohort_excludes_courses_i_am_already_in(client, register_user):
    me = await _register(register_user, program="Biology", entry_year=2025)
    peer = await _register(register_user, program="Biology", entry_year=2025)

    course = await _create_course(client, peer["headers"], code="BIO201")
    await _join(client, me["headers"], course["id"])  # I'm a member now

    assert await _cohort(client, me["headers"]) == []


async def test_cohort_ranked_by_peer_count(client, register_user):
    me = await _register(register_user, program="Biology", entry_year=2025)
    p1 = await _register(register_user, program="Biology", entry_year=2025)
    p2 = await _register(register_user, program="Biology", entry_year=2025)
    p3 = await _register(register_user, program="Biology", entry_year=2025)

    # popular: 3 cohort peers. quiet: 2 cohort peers.
    popular = await _create_course(client, p1["headers"], code="POP")
    await _join(client, p2["headers"], popular["id"])
    await _join(client, p3["headers"], popular["id"])

    quiet = await _create_course(client, p1["headers"], code="QUIET")
    await _join(client, p2["headers"], quiet["id"])

    discovered = await _cohort(client, me["headers"])
    assert [d["course_id"] for d in discovered] == [popular["id"], quiet["id"]]
    assert discovered[0]["signals"]["cohort_peers_here"] == 3
    assert discovered[1]["signals"]["cohort_peers_here"] == 2


async def test_cohort_does_not_enroll(client, register_user):
    me = await _register(register_user, program="Biology", entry_year=2025)
    peer = await _register(register_user, program="Biology", entry_year=2025)
    other = await _register(register_user, program="Biology", entry_year=2025)
    course = await _create_course(client, peer["headers"], code="BIO201")
    await _join(client, other["headers"], course["id"])

    discovered = await _cohort(client, me["headers"])
    assert course["id"] in [d["course_id"] for d in discovered]

    # Seeing it must not enroll me.
    listing = await client.get("/api/courses", headers=me["headers"])
    assert course["id"] not in [c["id"] for c in listing.json()["courses"]]


async def test_cohort_empty_without_school(client, register_user):
    # No school_name → no school_id → nothing to scope a cohort against.
    me = await register_user(program="Biology", entry_year=2025)
    peer = await _register(register_user, program="Biology", entry_year=2025)
    other = await _register(register_user, program="Biology", entry_year=2025)
    course = await _create_course(client, peer["headers"], code="BIO201")
    await _join(client, other["headers"], course["id"])

    assert await _cohort(client, me["headers"]) == []


async def test_cohort_without_program_relaxes_to_school_and_year(client, register_user):
    """A user missing the program signal still gets a cohort scoped by the signals
    they DO have (school + entry_year). Hard-filtering on an unknown would wrongly
    match every other unknown."""
    me = await _register(register_user, program=None, entry_year=2025)
    peer = await _register(register_user, program="Biology", entry_year=2025)
    other = await _register(register_user, program="Chemistry", entry_year=2025)

    course = await _create_course(client, peer["headers"], code="BIO201")
    await _join(client, other["headers"], course["id"])

    discovered = await _cohort(client, me["headers"])
    # Both share my school + entry_year; program isn't a filter for me.
    assert [d["course_id"] for d in discovered] == [course["id"]]
    assert discovered[0]["signals"]["cohort_peers_here"] == 2
