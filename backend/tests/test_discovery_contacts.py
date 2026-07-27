"""
Contact-match — "see which of your contacts are on NotesOS" (the final onboarding
beat). Contacts are uploaded as SHA-256 hashes of canonical phones; the endpoint
returns matched users and the activity-gated courses at your school they're in.

The contract under test:
- A contact is matched by the hash of their canonical phone — national vs.
  international formatting must not matter (the hash is over the canonical form).
- Each matched contact carries the courses they're in that YOU are not, scoped to
  your school and past the activity gate.
- Unknown hashes match nobody; you never match yourself.
- Notify-don't-enroll: matching never joins you to anything.
- Same-school contacts rank first.
"""

from app.services.phone import phone_hash

SCHOOL = "University of Lagos"


async def _register(register_user, *, phone=None, program=None, entry_year=None, school=SCHOOL):
    return await register_user(
        phone=phone, school_name=school, program=program, entry_year=entry_year
    )


async def _create_course(client, headers, code="BIO201", name=None):
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


async def _match(client, headers, hashes):
    resp = await client.post(
        "/api/discovery/contacts", headers=headers, json={"phone_hashes": hashes}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["contacts"]


async def test_matches_a_contact_by_phone_hash(client, register_user):
    me = await _register(register_user)
    friend = await _register(register_user, phone="+2348031234567")

    # I have my friend's number saved in national format — still the same hash.
    contacts = await _match(client, me["headers"], [phone_hash("08031234567")])

    assert [ct["id"] for ct in contacts] == [friend["id"]]


async def test_unknown_hashes_match_nobody(client, register_user):
    me = await _register(register_user)
    assert await _match(client, me["headers"], [phone_hash("+2340000000000")]) == []


async def test_does_not_match_self(client, register_user):
    me = await _register(register_user, phone="+2348031234567")
    # My own number is in my contacts — I must not match myself.
    assert await _match(client, me["headers"], [phone_hash("08031234567")]) == []


async def test_surfaces_contacts_active_course_i_can_join(client, register_user):
    me = await _register(register_user)
    friend = await _register(register_user, phone="+2348031234567")
    other = await _register(register_user)

    course = await _create_course(client, friend["headers"], code="CHEM101")
    await _join(client, other["headers"], course["id"])  # 2 members ⇒ active

    contacts = await _match(client, me["headers"], [phone_hash("+2348031234567")])
    assert len(contacts) == 1
    assert [c["course_id"] for c in contacts[0]["courses"]] == [course["id"]]
    assert contacts[0]["courses"][0]["member_count"] == 2


async def test_hides_contacts_solo_empty_course(client, register_user):
    me = await _register(register_user)
    friend = await _register(register_user, phone="+2348031234567")

    # Friend's solo, empty course — one member, no uploads. Activity gate hides it.
    await _create_course(client, friend["headers"], code="SOLO")

    contacts = await _match(client, me["headers"], [phone_hash("+2348031234567")])
    assert len(contacts) == 1
    assert contacts[0]["courses"] == []  # matched, but no joinable course


async def test_excludes_course_i_am_already_in(client, register_user):
    me = await _register(register_user)
    friend = await _register(register_user, phone="+2348031234567")
    other = await _register(register_user)

    course = await _create_course(client, friend["headers"], code="BIO201")
    await _join(client, other["headers"], course["id"])
    await _join(client, me["headers"], course["id"])  # I'm already in it

    contacts = await _match(client, me["headers"], [phone_hash("+2348031234567")])
    assert contacts[0]["courses"] == []


async def test_matching_does_not_enroll(client, register_user):
    me = await _register(register_user)
    friend = await _register(register_user, phone="+2348031234567")
    other = await _register(register_user)
    course = await _create_course(client, friend["headers"], code="BIO201")
    await _join(client, other["headers"], course["id"])

    contacts = await _match(client, me["headers"], [phone_hash("+2348031234567")])
    assert course["id"] in [c["course_id"] for c in contacts[0]["courses"]]

    listing = await client.get("/api/courses", headers=me["headers"])
    assert course["id"] not in [c["id"] for c in listing.json()["courses"]]


async def test_same_school_contacts_rank_first(client, register_user):
    me = await _register(register_user, school="University of Lagos")
    same = await _register(register_user, phone="+2348030000001", school="University of Lagos")
    away = await _register(register_user, phone="+2348030000002", school="University of Ibadan")

    contacts = await _match(
        client,
        me["headers"],
        [phone_hash("+2348030000002"), phone_hash("+2348030000001")],
    )
    ids = [ct["id"] for ct in contacts]
    assert ids == [same["id"], away["id"]]
    assert contacts[0]["same_school"] is True
    assert contacts[1]["same_school"] is False


async def test_empty_upload_returns_empty(client, register_user):
    me = await _register(register_user)
    assert await _match(client, me["headers"], []) == []
