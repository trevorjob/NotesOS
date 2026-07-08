"""
School canonicalisation — the first incarnation of the proximity check.

These seed a couple of schools directly (the test DB is built from models, not
the seed migration) and assert that exact keys, aliases, and fuzzy typos all
resolve to one canonical row rather than fragmenting.
"""

import pytest

from app.data.schools import normalize_school_name
from app.models.school import School
from app.services.school import find_or_create_school, find_school


@pytest.fixture
async def unilag(db_session):
    school = School(
        name="University of Lagos",
        normalized_name=normalize_school_name("University of Lagos"),
        country="NG",
        aliases=[normalize_school_name("Unilag")],
    )
    db_session.add(school)
    # Commit (not just flush) so the separate session behind the HTTP client can
    # see it in test_school_search_endpoint.
    await db_session.commit()
    return school


def test_normalize_collapses_case_and_punctuation():
    assert normalize_school_name("University of Lagos") == "university of lagos"
    assert normalize_school_name("  UNILAG ") == "unilag"
    assert normalize_school_name("University of Nigeria, Nsukka") == "university of nigeria nsukka"


async def test_exact_normalized_match(db_session, unilag):
    found = await find_school(db_session, "university of lagos")
    assert found is not None
    assert found.id == unilag.id


async def test_case_and_spacing_insensitive_match(db_session, unilag):
    found = await find_school(db_session, "  University   Of  LAGOS ")
    assert found is not None and found.id == unilag.id


async def test_alias_match(db_session, unilag):
    found = await find_school(db_session, "UNILAG")
    assert found is not None and found.id == unilag.id


async def test_fuzzy_typo_matches_existing(db_session, unilag):
    # A typo close enough on trgm similarity should resolve, not fork.
    found = await find_school(db_session, "Univrsity of Lagos")
    assert found is not None and found.id == unilag.id


async def test_unrelated_name_does_not_match(db_session, unilag):
    assert await find_school(db_session, "Harvard University") is None


async def test_find_or_create_reuses_existing(db_session, unilag):
    resolved = await find_or_create_school(db_session, "unilag")
    assert resolved.id == unilag.id


async def test_find_or_create_creates_when_absent(db_session):
    created = await find_or_create_school(db_session, "Some New Polytechnic", country="NG")
    assert created is not None
    assert created.normalized_name == "some new polytechnic"

    # A second lookup must resolve to the same row, not a duplicate.
    again = await find_or_create_school(db_session, "some new  polytechnic")
    assert again.id == created.id


async def test_find_or_create_blank_returns_none(db_session):
    assert await find_or_create_school(db_session, "   ") is None


async def test_school_search_endpoint(client, db_session, unilag):
    resp = await client.get("/api/schools/search", params={"q": "unil"})
    assert resp.status_code == 200, resp.text
    names = [s["name"] for s in resp.json()["schools"]]
    assert "University of Lagos" in names
